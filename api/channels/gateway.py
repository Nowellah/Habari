"""Channel gateway: every channel turns its message into the same call here.

State machine per reporter and channel:
    START -> PICK_HARM -> DESCRIBE -> (PICK_LANG) -> CASE_OPEN
Pick 1, or a danger phrase at any point, creates a severity 4 case at once and
the reply starts with the helpline.
PICK_LANG is asked once, after the case exists, when the language is unclear.
Commands work in any state: HELP, STATUS <code> [word], STOP, PIN <word>.
AI triage runs in the background after each reply (core.ai_triage).
"""
import hashlib
import hmac
import logging
import re
import time
from contextvars import ContextVar

from django.conf import settings
from django.db import IntegrityError, transaction

from ai_service.engine import retrieval
from channels import proofs
from ai_service.engine.config import get_settings as knowledge_settings
from ai_service.language import detect_language
from core import ai_client, ai_triage, followup, sla
from core.harm import pick_severity, picks
from core.messages import _messages, label, reply_languages
from core.messages import msg as _msg
from core.messages import status_words
from core.models import Case, Conversation, Message, Reporter, ReporterVault
from core.triage_rules import apply_rules
from core.utils import PHONE_CHANNELS, new_case_code, normalise_msisdn, pseudo_id

MENU_WORDS = {"HELP", "MENU", "START", "/START", "HI", "HELLO"}
RATINGS = {"1": "good", "2": "ok", "3": "not_good", "😀": "good", "🙂": "good", "😐": "ok", "😞": "not_good"}
FEELINGS = {"1": "little", "2": "lot", "3": "scared", "4": "danger"}
# What the child says they feel is a floor: it can raise severity, never lower it.
FEELING_FLOOR = {"little": 1, "lot": 2, "scared": 3, "danger": 4}
# Button labels are keys into the "labels" table of shared/messages_<lang>.json.
FEELING_LABELS = {"1": "feel_little", "2": "feel_lot", "3": "feel_scared", "4": "feel_danger", "0": "skip"}
SAFE_OPTIONS = {"1": "safe_yes", "2": "safe_no", "3": "not_sure"}
SOURCE_OPTIONS = {"1": "from_known", "2": "from_online", "3": "from_authority", "4": "from_self", "5": "not_sure"}
SOURCE_FLAGS = {"1": "danger_from_known", "2": "danger_from_online", "3": "danger_from_authority",
                "4": "danger_from_self", "5": "danger_from_unsure"}
OFFER_LABELS = {"TALK": "offer_talk", "REPORT": "offer_report", "PROOF": "offer_proof", "ASK": "offer_ask"}
WEB_START_WORDS = {"MENU", "START", "/START", "HI", "HELLO"}
EVIDENCE_ENTRY_ID = "keep-evidence"
HURT_OPTIONS = {"1": "Yes, I am hurt", "2": "No, I am not hurt", "3": "Not sure"}
HARM_BY_PERSON_FLAGS = {"harm_by_person", "rule:abuse_sexual_or_physical"}
PROOF_ANSWERS = {"PROOF_LATER": "proof_later", "PROOF_DONE": "proof_done", "PROOF_RIGHT": "proof_right"}
NEXT_STEPS = re.compile(r"\b(what (do|should|can) i do|what now|what next|what happens next|help me)\b")
LANG_OPTIONS = {"1": ("lg", "Luganda"), "2": ("rn", "Runyankore"), "3": ("sw", "Swahili"), "4": ("en", "English")}


logger = logging.getLogger("habari.ai")

QUESTION_STARTS = {"what", "how", "why", "can", "could", "is", "are", "am", "do", "does", "did", "should",
                   "will", "who", "when", "where", "which"}

_channel = ContextVar("channel", default="")
_lang = ContextVar("lang", default="en")  # the language this reply is written in

# A child who greets us in Luganda is answered in Luganda (draft list, needs native review).
LUGANDA_GREETINGS = {"oli otya", "gyebale ko", "gyebale", "osiibye otya", "wasuze otya", "ki kati",
                     "nkwetaaga obuyambi", "nnyamba", "mbeera", "obuyambi"}


def msg(key, lang=None, **kw):
    """The wording for the channel and language being served.

    The web chat has its own short, child-friendly version (key_web). The child's language
    wins over the web version, so a Luganda text is never swapped for an English one.
    """
    lang = lang if lang in reply_languages() else _lang.get()
    keys = (f"{key}_web", key) if _channel.get() == "web" else (key,)
    for source_lang in dict.fromkeys((lang, "en")):
        for k in keys:
            if k in _messages(source_lang):
                return _msg(k, source_lang, **kw)
    return _msg(key, "en", **kw)


def L(name):
    """A button label in the language of this reply."""
    return label(name, _lang.get())


def _words(text):
    return " ".join(re.sub(r"[^\w\s']", " ", (text or "").lower()).split())


def _reply_language(reporter, text, language):
    """Pick the language to answer in, and remember it on the reporter.

    Order: a language the channel told us, a Luganda greeting, a message we can confidently
    place, then what the child chose or wrote before. Short or unclear text keeps the last one.
    """
    supported = reply_languages()
    if language in supported:
        return language
    lowered = _words(text)
    detected = None
    if lowered in LUGANDA_GREETINGS:
        detected = "lg"
    elif len(lowered.split()) >= 3:
        guess = detect_language(lowered)
        if not guess["ask_language"] and guess["language"] in supported:
            detected = guess["language"]
    if detected and detected != reporter.language:
        reporter.language = detected
        reporter.save(update_fields=["language"])
    current = detected or reporter.language
    return current if current in supported else "en"


def _join(*parts):
    """SMS keeps one running text. The web chat shows each part as its own bubble."""
    return ("\n\n" if _channel.get() == "web" else " ").join(p for p in parts if p)


def _reply(text, state, case=None, options=None):
    return {"reply_text": text, "options": options or [], "case_code": case.code if case else None, "state": state}


def _for_buttons(out):
    """Web chat shows buttons, so the typed list of numbers used by SMS is removed from the text."""
    if not out["options"] and out["state"] != "DESCRIBE":
        return out
    text = out["reply_text"]
    if text == msg("menu"):
        text = msg("menu_web")
    elif text == msg("menu_retry"):
        text = msg("menu_said_web")
    text = re.sub(r"^Habari:\s*", "", text)
    cut = re.search(r"\s*(Reply|Ddamu)\s+\d|\s[0-9]\s+[A-Z]", text)
    if cut:
        text = text[:cut.start()].rstrip()
    out = dict(out, reply_text=text)
    if out["state"] == "DESCRIBE":
        out["options"] = [{"key": "0", "label": L("skip")}]
    return out


AGE_BRACKETS = {"under_10", "10_12", "13_15", "16_17"}


def _record_age(case_code, meta):
    """Keep the age group the child chose as a flag on the case. Skipping it is fine."""
    age = meta.get("age_bracket") if isinstance(meta, dict) else None
    if age not in AGE_BRACKETS:
        return
    case = Case.objects.get(code=case_code)
    flag = f"age_{age}"
    if flag not in case.flags:
        case.flags = sorted(set(case.flags) | {flag})
        case.save(update_fields=["flags"])


def _menu_options():
    lang = _lang.get()
    return [{"key": k, "label": p.get(f"short_{lang}") or p["short_en"]} for k, p in picks().items()]


def _feeling_options():
    return [{"key": k, "label": L(name)} for k, name in FEELING_LABELS.items()]


def apply_feeling(case, feeling):
    """Record how the child says it feels. Returns the severity the case had before."""
    was = case.severity
    case.flags = sorted(set(case.flags) | {f"child_feels_{feeling}"})
    case.severity = max(was, FEELING_FLOOR[feeling])
    case.save(update_fields=["flags", "severity"])
    if case.severity > was:
        sla.reset_clock(case, f"severity raised {was} -> {case.severity}")
        sla.once(case, "severity_raised", f"{was} -> {case.severity}: child said how it feels")
        ai_triage.schedule(case.id)
    return was


def _danger_options(labels):
    return [{"key": k, "label": L(name)} for k, name in labels.items()]


def _start_danger_questions(conv, case, lead):
    """The helpline comes first. Then, where there is room for it, ask what the danger is.

    Severity is already the highest, so the answers only add detail for the helper.
    Basic phones (SMS, USSD) are not asked, to keep their messages short.
    """
    if case.channel in ("sms", "ussd"):
        conv.state, conv.case, conv.draft = "CASE_OPEN", case, {}
        conv.save()
        return _reply(lead, "CASE_OPEN", case)
    conv.state, conv.case, conv.draft = "CASE_OPEN", case, {"awaiting": "danger", "step": 1}
    conv.save()
    return _reply(_join(lead, msg("danger_q_safe")), "CASE_OPEN", case, _danger_options(SAFE_OPTIONS))


def _ask_if_hurt(conv, case):
    """The child said someone hurt them. Say it is not their fault, then ask if they are hurt."""
    case.flags = sorted(set(case.flags) | {"asked_hurt"})
    case.save(update_fields=["flags"])
    conv.state, conv.case, conv.draft = "CASE_OPEN", case, {"awaiting": "hurt"}
    conv.save()
    return _reply(_join(msg("hurt_sorry"), msg("hurt_notfault"), msg("hurt_ask")), "CASE_OPEN", case,
                  _danger_options(HURT_OPTIONS))


def _answer_hurt(conv, text):
    """Handle the reply to "Are you hurt?". None means it was more information instead."""
    conv.draft = {}
    conv.save()
    if text not in HURT_OPTIONS:
        return None
    case = conv.case
    if text == "1":
        was = case.severity
        case.flags = sorted(set(case.flags) | {"child_hurt"})
        case.severity = max(was, 4)
        case.save(update_fields=["flags", "severity"])
        if case.severity > was:
            sla.reset_clock(case, f"severity raised {was} -> {case.severity}")
            sla.once(case, "severity_raised", f"{was} -> {case.severity}: child said they are hurt")
            ai_triage.schedule(case.id)
        return _reply(_join(msg("hurt_yes_sorry"), msg("hurt_yes_clinic"), msg("hurt_yes_call")), "CASE_OPEN", case)
    return _reply(_join(msg("hurt_no_glad"), msg("hurt_no_next")), "CASE_OPEN", case)


def _answer_danger(conv, text):
    """Handle the follow-up questions after a danger report. None means it was more information instead."""
    case, step = conv.case, (conv.draft or {}).get("step", 1)
    if step == 1 and text in SAFE_OPTIONS:
        lead = ""
        if text == "2":
            case.flags = sorted(set(case.flags) | {"child_not_safe"})
            case.save(update_fields=["flags"])
            lead = msg("danger_unsafe")
        conv.draft = {"awaiting": "danger", "step": 2}
        conv.save()
        return _reply(_join(lead, msg("danger_q_from")), "CASE_OPEN", case, _danger_options(SOURCE_OPTIONS))
    if step == 2 and text in SOURCE_OPTIONS:
        case.flags = sorted(set(case.flags) | {SOURCE_FLAGS[text]})
        if text == "3" and not case.alleged_role:
            case.alleged_role = "authority"
        case.save(update_fields=["flags", "alleged_role"])
        conv.draft = {"awaiting": "danger", "step": 3}
        conv.save()
        return _reply(msg("danger_q_tell"), "CASE_OPEN", case, [{"key": "0", "label": L("skip")}])
    conv.draft = {}
    conv.save()
    if step == 3 and text == "0":
        return _with_proof_ask(msg("danger_thanks"), "CASE_OPEN", case)
    return None


def _answer_feeling(conv, text):
    """Handle the reply to the feeling question. None means it was more information instead."""
    conv.draft = {}
    conv.save()
    if text == "0":
        return _with_proof_ask(msg("feeling_thanks"), "CASE_OPEN", conv.case)
    feeling = FEELINGS.get(text)
    if feeling is None:
        return None
    case = conv.case
    apply_feeling(case, feeling)
    if case.severity >= 4:
        return _start_danger_questions(conv, case, msg("danger", code=case.code))
    if feeling == "little" and case.severity >= 3:
        return _with_proof_ask(msg("feeling_higher"), "CASE_OPEN", case)
    return _with_proof_ask(msg("feeling_thanks"), "CASE_OPEN", case)


def get_reporter(channel, sender_id, language):
    rep, created = Reporter.objects.get_or_create(
        pseudo_id=pseudo_id(channel, sender_id, settings.HMAC_SECRET),
        defaults={"channel": channel, "basic_phone": channel in ("sms", "ussd")},
    )
    changed = False
    if rep.opted_out:  # the child wrote to us again, so they are back in
        rep.opted_out, changed = False, True
    if language and rep.language != language:
        rep.language, changed = language, True
    if changed:
        rep.save()
    if channel in PHONE_CHANNELS:
        ReporterVault.objects.update_or_create(reporter=rep, defaults={"raw_contact": normalise_msisdn(sender_id)})
    elif channel == "telegram":  # needed to send follow-ups; web channels have no address to keep
        ReporterVault.objects.update_or_create(reporter=rep, defaults={"raw_contact": sender_id})
    return rep


def _pin_hash(reporter, word):
    key = f"pin:{reporter.pseudo_id}:{word.strip().lower()}"
    return hmac.new(settings.HMAC_SECRET.encode(), key.encode(), hashlib.sha256).hexdigest()


def create_case(reporter, channel, pick, text, language):
    """Create a case from rules only, then queue AI triage for after the reply."""
    rules = apply_rules(text, pick)
    for _ in range(5):
        try:
            with transaction.atomic():
                case = Case.objects.create(
                    code=new_case_code(), reporter=reporter, channel=channel, pick=pick or "",
                    severity=max(rules.severity, pick_severity(pick)), flags=rules.flags,
                    alleged_role="authority" if (pick == "3" or rules.role_hint) else "",
                    language=language or reporter.language,
                    district=reporter.district,
                )
            break
        except IntegrityError:  # code collision, try another
            continue
    else:
        raise RuntimeError("could not allocate a case code")
    if text:
        Message.objects.create(case=case, direction="in", text=text, channel=channel)
    ai_triage.schedule(case.id)
    return case


def _should_ask_language(case, text, reporter, language):
    if case.severity >= 4 or language or reporter.language or not text:
        return False  # danger replies stay short; never ask twice
    return detect_language(text)["ask_language"]


SEXTORTION_SIGNS = ("sextortion", "rule:sextortion_threat", "rule:sextortion_payment_demand")


def _advice(case):
    """What to do right now, for the harms where the first minutes matter."""
    if case.category == "sextortion" or any(f in case.flags for f in SEXTORTION_SIGNS):
        return msg("advice_sextortion")
    return ""


def _case_reply(case, conv, text="", language=None):
    if case.severity < 4 and _should_ask_language(case, text, case.reporter, language):
        conv.state, conv.case, conv.draft = "PICK_LANG", case, {}
        conv.save()
        options = [{"key": k, "label": name} for k, (_, name) in LANG_OPTIONS.items()]
        return _reply(_join(msg("received", code=case.code), _advice(case), msg("lang_question")),
                      "PICK_LANG", case, options)
    if case.severity >= 4:  # the helpline first, then what the danger is
        return _start_danger_questions(conv, case, _join(msg("danger", code=case.code), _advice(case)))
    conv.state, conv.case, conv.draft = "CASE_OPEN", case, {"awaiting": "feeling"}
    conv.save()
    return _reply(_join(msg("received", code=case.code), _advice(case), msg("feeling_ask")),
                  "CASE_OPEN", case, _feeling_options())


def _knowledge_answer(channel, text, language):
    """A reviewed answer for a plain question on the English web chat. Nothing is generated.

    Never used for anything that matches a harm rule: that is a report, not a question.
    """
    if channel != "web" or _lang.get() != "en":
        return None
    lowered = text.strip().lower()
    if not (lowered.endswith("?") or lowered.split()[0] in QUESTION_STARTS):
        return None
    return _lookup_answer(text)


def _lookup_answer(text):
    """The best reviewed answer for the text, or None. Nothing is generated."""
    try:
        match = retrieval.search(text, "en", knowledge_settings()).match
    except Exception as exc:  # noqa: BLE001 - answers are optional, the menu still works
        logger.error("knowledge lookup failed with %s", type(exc).__name__)
        return None
    return match.entry.answer if match else None


def _entry_answer(entry_id):
    kb = retrieval.load_knowledge_base("en")
    entry = next((e for e in kb.entries if e.id == entry_id), None) if kb else None
    return entry.answer if entry else None


def _offer_options():
    return [{"key": k, "label": L(name)} for k, name in OFFER_LABELS.items()]


def _proof_options():
    return [{"key": "PROOF_ADD", "label": L("proof_add")}, {"key": "PROOF_LATER", "label": L("proof_later")}]


def _with_proof_ask(text, state, case):
    """On the web chat, finish a reply by asking for screenshots. Other channels cannot upload files."""
    if _channel.get() != "web":
        return _reply(text, state, case)
    return _reply(_join(text, msg("proof_ask"), msg("proof_warn")), state, case, _proof_options())


def _case_question_reply(case, text, language):
    """A real answer when the child asks something after the report is made. None means carry on as usual."""
    lowered = text.strip().lower()
    if not lowered:
        return None
    wants_steps = bool(NEXT_STEPS.search(lowered))
    if not (wants_steps or lowered.endswith("?") or lowered.split()[0] in QUESTION_STARTS):
        return None
    steps = _join(msg("next_steps"), msg("next_keep"), msg("next_dont"), msg("next_adult"), msg("next_helper"))
    # A short "what do I do now" gets the plain steps; a longer, specific question gets its reviewed answer first.
    if wants_steps and len(lowered.split()) <= 6:
        answer = steps
    else:
        answer = (_lookup_answer(text) if _lang.get() == "en" else None) or (steps if wants_steps else None)
    if not answer:
        return None
    if case.evidence.filter(kind=proofs.KIND).exists():
        return _reply(answer, "CASE_OPEN", case)
    return _with_proof_ask(answer, "CASE_OPEN", case)


def _after_answer_options():
    return [{"key": "REPORT", "label": L("tell_something")}, {"key": "MENU", "label": L("back_to_menu")}]


def _status(reporter, conv, args):
    if args:
        case = Case.objects.filter(code__iexact=args[0]).first()
        if not case:
            return _reply(msg("status_unknown"), conv.state if conv else "START")
    else:
        case = (conv and conv.case) or reporter.cases.order_by("-created_at").first()
        if not case:
            return _reply(msg("status_need_code"), conv.state if conv else "START")
    owner = case.reporter
    if owner and owner.pin_hash:
        word = args[1] if len(args) > 1 else ""
        if not word or not hmac.compare_digest(_pin_hash(owner, word), owner.pin_hash):
            return _reply(msg("status_need_pin", code=case.code), conv.state if conv else "START")
    return _reply(status_words(case, _lang.get()), conv.state if conv else "START", case)


def _stop(reporter):
    reporter.conversations.all().delete()
    ReporterVault.objects.filter(reporter=reporter).delete()
    reporter.opted_out = True
    reporter.save()
    return _reply(msg("stopped"), "START")


def _set_district(reporter, conv, district):
    """Keep the district on the child and on their open case. Never coordinates."""
    reporter.district = district
    reporter.save(update_fields=["district"])
    if conv and conv.case and not conv.case.district:
        conv.case.district = district
        conv.case.save(update_fields=["district"])


def _route(channel, reporter, text, language):
    words = text.split()
    command = words[0].upper() if words else ""
    conv = reporter.conversations.filter(channel=channel).order_by("-updated_at").first()

    if command == "STATUS":
        return _status(reporter, conv, words[1:])
    if command == "STOP":
        return _stop(reporter)
    if command == "DISTRICT":
        from core.geo import district_by_name
        found = district_by_name(" ".join(words[1:]))
        if not found:
            return _reply(msg("district_unknown"), conv.state if conv else "START")
        _set_district(reporter, conv, found)
        return _reply(msg("location_saved", district=found), conv.state if conv else "START")
    if command == "JOIN" and len(words) == 1:
        reporter.poll_opt_in = True
        reporter.save(update_fields=["poll_opt_in"])
        return _reply(msg("poll_joined"), conv.state if conv else "START")
    if command == "PIN":
        if len(words) < 2:
            return _reply(msg("pin_need_word"), conv.state if conv else "START")
        reporter.pin_hash = _pin_hash(reporter, words[1])
        reporter.save()
        return _reply(msg("pin_saved"), conv.state if conv else "START")

    if conv is None:
        conv = Conversation.objects.create(reporter=reporter, channel=channel)

    if conv.state == "POLL":
        from polls.models import Poll
        from polls.service import record_answer
        poll = Poll.objects.filter(pk=(conv.draft or {}).get("poll")).first()
        conv.state, conv.draft = "START", {}
        conv.save()
        if poll and text.isdigit() and 1 <= int(text) <= len(poll.options):
            answer = poll.options[int(text) - 1]
            record_answer(poll, reporter, answer)
            # The first option ("Yes") gently invites a conversation. No case is made.
            return _reply(msg("poll_yes" if text == "1" else "poll_thanks"), "START")
        # anything else: carry on as a normal message

    if conv.state == "VOICE_CONFIRM":
        # "1" sends what we heard; anything else is the child's own typed words.
        draft = conv.draft or {}
        conv.state, conv.draft = draft.get("prev_state", "START"), draft.get("prev_draft", {})
        conv.save()
        via_voice = text == "1"
        out = _route(channel, reporter, draft.get("voice_text", "") if via_voice else text, language)
        if via_voice and out.get("case_code"):
            case = Case.objects.get(code=out["case_code"])
            case.flags = sorted(set(case.flags) | {"via_voice"})
            case.save(update_fields=["flags"])
        return out

    def open_menu(key="menu"):
        conv.state, conv.case, conv.draft = "PICK_HARM", None, {}
        conv.save()
        return _reply(msg(key), "PICK_HARM", options=_menu_options())

    if channel == "web" and len(words) == 1 and command in PROOF_ANSWERS and conv.case:
        if command != "PROOF_RIGHT":  # they said they have nothing more to add, so do not ask again
            conv.case.flags = sorted(set(conv.case.flags) | {"share_done"})
            conv.case.save(update_fields=["flags"])
        return _reply(msg(PROOF_ANSWERS[command]), conv.state, conv.case)

    if channel == "web" and len(words) == 1:
        if command in WEB_START_WORDS:
            conv.state, conv.case, conv.draft = "OFFER", None, {}
            conv.save()
            return _reply(msg("offer"), "OFFER", options=_offer_options())
        if command in OFFER_LABELS and conv.state in ("OFFER", "ASK", "START", "PICK_HARM"):
            return _offer_choice(conv, command, open_menu)

    # Only a lone "HELP" opens the menu; "help me, he wants..." is a description.
    if _words(text) in LUGANDA_GREETINGS and channel == "web":
        conv.state, conv.case, conv.draft = "OFFER", None, {}
        conv.save()
        return _reply(msg("offer"), "OFFER", options=_offer_options())
    if (command in MENU_WORDS and len(words) == 1) or _words(text) in LUGANDA_GREETINGS:
        return open_menu()

    danger = apply_rules(text).severity >= 4

    if conv.state == "PICK_LANG" and conv.case:
        if text in LANG_OPTIONS:
            code, name = LANG_OPTIONS[text]
            case = conv.case
            case.language, case.language_conf = code, 1.0
            case.save(update_fields=["language", "language_conf"])
            reporter.language = code
            reporter.save(update_fields=["language"])
            _lang.set(code if code in reply_languages() else "en")
            conv.state, conv.draft = "CASE_OPEN", {"awaiting": "feeling"}
            conv.save()
            return _reply(_join(msg("lang_saved", language=name), msg("feeling_ask")), "CASE_OPEN", case,
                          _feeling_options())
        conv.state = "CASE_OPEN"  # they wrote something else: treat it as more information
        conv.save()

    if conv.state == "CASE_OPEN" and conv.case and (conv.draft or {}).get("awaiting") == "feeling":
        answered = _answer_feeling(conv, text)
        if answered:
            return answered

    if conv.state == "CASE_OPEN" and conv.case and (conv.draft or {}).get("awaiting") == "danger":
        answered = _answer_danger(conv, text)
        if answered:
            return answered

    if conv.state == "CASE_OPEN" and conv.case and (conv.draft or {}).get("awaiting") == "hurt":
        answered = _answer_hurt(conv, text)
        if answered:
            return answered

    if conv.state == "CHECKIN" and conv.case:
        case = conv.case
        if text == "1":
            conv.state = "RATE"
            conv.save()
            return _reply(msg("checkin_rate"), "RATE", case,
                          [{"key": "1", "label": L("rate_good")}, {"key": "2", "label": L("rate_ok")}, {"key": "3", "label": L("rate_bad")}])
        if text in ("2", "3"):
            Message.objects.create(case=case, direction="in", text=f"Check-in answer: {text} (not safe)", channel=channel)
            case.flags = sorted(set(case.flags) | {"child_not_safe"})
            was = case.severity
            case.severity = max(case.severity, 3)
            case.save(update_fields=["flags", "severity"])
            followup.reopen(case, "child said they are not safe")
            if case.severity > was:
                sla.once(case, "severity_raised", f"{was} -> {case.severity}: child not safe")
            conv.state = "CASE_OPEN"
            conv.save()
            return _reply(msg("not_safe"), "CASE_OPEN", case)
        conv.state = "CASE_OPEN"  # anything else is more information

    if conv.state == "RATE" and conv.case:
        conv.state = "CASE_OPEN"
        conv.save()
        if text in RATINGS:
            conv.case.rating = RATINGS[text]
            conv.case.save(update_fields=["rating"])
            return _reply(msg("rating_saved"), "CASE_OPEN", conv.case)

    if conv.state == "CASE_OPEN" and conv.case:
        case = conv.case
        Message.objects.create(case=case, direction="in", text=text, channel=channel)
        if case.status in followup.CLOSED or case.status in (Case.Status.RESOLVED, Case.Status.SAFETY_CHECK):
            followup.reopen(case, "child sent new information")
        rules = apply_rules(text, case.pick)
        was = case.severity
        case.severity = max(case.severity, rules.severity)
        case.flags = sorted(set(case.flags) | set(rules.flags))
        if rules.role_hint and not case.alleged_role:
            case.alleged_role = rules.role_hint
        case.save()
        if case.severity > was:
            sla.reset_clock(case, f"severity raised {was} -> {case.severity}")
            sla.once(case, "severity_raised", f"{was} -> {case.severity}: new message")
        ai_triage.schedule(case.id)
        if case.severity >= 4 and was < 4:
            return _start_danger_questions(conv, case, msg("danger", code=case.code))
        if channel == "web" and "asked_hurt" not in case.flags and HARM_BY_PERSON_FLAGS & set(apply_rules(text).flags):
            return _ask_if_hurt(conv, case)
        if channel == "web":
            helped = _case_question_reply(case, text, language)
            if helped:
                return helped
        if channel == "web" and "share_done" not in case.flags:
            return _reply(_join(msg("added", code=case.code), msg("share_more")), "CASE_OPEN", case,
                          [{"key": "PROOF_ADD", "label": "Add screenshots"}, {"key": "PROOF_DONE", "label": "That is all"}])
        return _reply(msg("added", code=case.code), "CASE_OPEN", case)

    if conv.state == "DESCRIBE":
        pick = conv.draft.get("pick")
        description = "" if text == "0" else text
        case = create_case(reporter, channel, pick, description, language)
        return _case_reply(case, conv, description, language)

    if conv.state == "PICK_HARM" and text in picks():
        said = (conv.draft or {}).get("said", "")
        if said:  # the child already described it, so the pick completes the report
            return _case_reply(create_case(reporter, channel, text, said, language), conv, said, language)
        if text == "1":
            return _case_reply(create_case(reporter, channel, "1", "", language), conv)
        conv.state, conv.draft = "DESCRIBE", {"pick": text}
        conv.save()
        return _reply(msg("describe"), "DESCRIBE")

    if conv.state == "ASK" and not danger:
        if apply_rules(text).flags:  # they are describing something that happened, so it is a report
            return _case_reply(create_case(reporter, channel, "5", text, language), conv, text, language)
        answer = _lookup_answer(text) if _lang.get() == "en" else None
        if answer:
            return _reply(_join(answer, msg("answer_follow")), "ASK", options=_after_answer_options())
        return _reply(_join(msg("ask_none"), msg("ask_none_help")), "ASK", options=_after_answer_options())

    if danger:  # a danger phrase skips the menu, in START or PICK_HARM
        return _case_reply(create_case(reporter, channel, "1", text, language), conv)

    if conv.state in ("START", "PICK_HARM", "OFFER") and len(words) >= 3:
        # Someone who simply tells us what happened is not sent back to a menu.
        if apply_rules(text).flags:
            return _case_reply(create_case(reporter, channel, "5", text, language), conv, text, language)
        answer = _knowledge_answer(channel, text, language)
        if answer:
            conv.state, conv.draft = "START", {}
            conv.save()
            return _reply(_join(answer, msg("answer_follow")), "START", options=_after_answer_options())
        conv.state, conv.draft = "PICK_HARM", {"said": text}
        conv.save()
        return _reply(msg("menu_retry"), "PICK_HARM", options=_menu_options())

    return open_menu("menu_retry" if conv.state == "PICK_HARM" else "menu")


def _offer_choice(conv, choice, open_menu):
    """One of the four first choices on the web chat."""
    if choice == "REPORT":
        return open_menu("menu_pick")
    if choice == "TALK":
        conv.state, conv.draft = "START", {}
        conv.save()
        return _reply(_join(msg("talk_call"), msg("talk_here")), "START",
                      options=[{"key": "REPORT", "label": L("write_here")}, {"key": "MENU", "label": L("back_to_menu")}])
    if choice == "PROOF":
        conv.state, conv.draft = "START", {}
        conv.save()
        return _reply(_entry_answer(EVIDENCE_ENTRY_ID) or msg("ask_none_help"), "START", options=_after_answer_options())
    conv.state, conv.draft = "ASK", {}
    conv.save()
    return _reply(msg("ask_question"), "ASK", options=[{"key": "MENU", "label": L("back_to_menu")}])


def _keep_voice_notes(reporter, channel, out, notes):
    """Attach voice notes to the case once it exists. Until then they wait in the conversation."""
    from channels import voice_notes
    if out.get("case_code"):
        voice_notes.attach(Case.objects.get(code=out["case_code"]), notes)
        notes = []
    conv = reporter.conversations.filter(channel=channel).order_by("-updated_at").first()
    if conv is not None:
        draft = {k: v for k, v in (conv.draft or {}).items() if k != "voice_pending"}
        if notes:
            draft["voice_pending"] = notes
        if draft != (conv.draft or {}):
            conv.draft = draft
            conv.save()


def handle(channel, sender_id, text="", language=None, attachments=None, location=None, meta=None,
           voice_note=None) -> dict:
    """Single entry point for every channel adapter. Returns the gateway response contract."""
    started = time.perf_counter()
    _channel.set(channel)
    with transaction.atomic():
        reporter = get_reporter(channel, str(sender_id), language)
        text = (text or "").strip()
        _lang.set(_reply_language(reporter, text, language))
        if isinstance(location, dict):
            from core.geo import nearest_district
            district = nearest_district(location.get("lat"), location.get("lon"))  # coordinates end here
            conv = reporter.conversations.filter(channel=channel).order_by("-updated_at").first()
            if district:
                _set_district(reporter, conv, district)
            if not text:
                key = "location_saved" if district else "location_unknown"
                out = _reply(msg(key, district=district or ""), conv.state if conv else "START",
                             conv.case if conv else None)
                out["first_reply_ms"] = round((time.perf_counter() - started) * 1000)
                return out
        prior = reporter.conversations.filter(channel=channel).order_by("-updated_at").first()
        waiting_notes = list((prior.draft or {}).get("voice_pending", [])) if prior else []
        out = _route(channel, reporter, text, language)
        if voice_note or waiting_notes:
            _keep_voice_notes(reporter, channel, out, waiting_notes + ([voice_note] if voice_note else []))
        if channel == "web":
            out = _for_buttons(out)
        if out.get("case_code") and meta:
            _record_age(out["case_code"], meta)
            from channels.meta_evidence import attach_meta
            attach_meta(Case.objects.get(code=out["case_code"]), meta)
    out["first_reply_ms"] = round((time.perf_counter() - started) * 1000)
    return out


def _proof_check(case, image, content_type):
    """Compare a proof picture with what the child reported. None when no check is set up."""
    if image is None:
        return None
    latest = list(case.messages.filter(direction="in").order_by("-id").values_list("text", flat=True)[:5])
    said = " ".join(reversed(latest))
    return ai_client.check_proof(image, content_type, said, (picks().get(case.pick) or {}).get("short_en", ""))


def add_proof(sender_id, note, image=None):
    """Put an uploaded proof file on the child's open case. Returns (reply, kept).

    `image` is the picture's bytes when it can be checked against the report.
    """
    _channel.set("web")
    with transaction.atomic():
        reporter = Reporter.objects.filter(pseudo_id=pseudo_id("web", str(sender_id), settings.HMAC_SECRET)).first()
        conv = reporter.conversations.filter(channel="web").order_by("-updated_at").first() if reporter else None
        case = conv.case if conv else None
        if case is None:
            return _for_buttons(_reply(msg("proof_need_case"), "START")), False
        check = _proof_check(case, image, note.get("type", ""))
        proofs.attach(case, proofs.checked(note, check))
        if case.status in followup.CLOSED or case.status in (Case.Status.RESOLVED, Case.Status.SAFETY_CHECK):
            followup.reopen(case, "child added proof")
        _lang.set(reporter.language if reporter.language in reply_languages() else "en")
        more = [{"key": "PROOF_ADD", "label": L("proof_more")}, {"key": "PROOF_DONE", "label": L("proof_done")}]
        flag = "proof_sensitive" if check and check["sensitive"] else "proof_unclear" if check and check["relevant"] == "no" else ""
        if flag:
            case.flags = sorted(set(case.flags) | {flag})
            case.save(update_fields=["flags"])
        if flag == "proof_sensitive":
            reply = _reply(msg("proof_sensitive"), conv.state, case, more)
        elif flag == "proof_unclear":
            reply = _reply(_join(msg("proof_unclear"), msg("proof_unclear_ask")), conv.state, case,
                           [{"key": "PROOF_RIGHT", "label": L("proof_right")}, {"key": "PROOF_ADD", "label": L("proof_another")}])
        else:
            reply = _reply(msg("proof_saved"), conv.state, case, more)
        return _for_buttons(reply), True


def handle_voice_transcript(channel, sender_id, transcript, language=None) -> dict:
    """Show the child what we heard. Nothing is sent until they reply 1 (or type)."""
    started = time.perf_counter()
    with transaction.atomic():
        reporter = get_reporter(channel, str(sender_id), language)
        _lang.set(_reply_language(reporter, transcript, language))
        conv = reporter.conversations.filter(channel=channel).order_by("-updated_at").first()             or Conversation.objects.create(reporter=reporter, channel=channel)
        conv.draft = {"voice_text": transcript, "prev_state": conv.state, "prev_draft": conv.draft}
        conv.state = "VOICE_CONFIRM"
        conv.save()
        out = _reply(msg("voice_confirm", text=transcript), "VOICE_CONFIRM", conv.case,
                     [{"key": "1", "label": L("send_it")}])
    out["first_reply_ms"] = round((time.perf_counter() - started) * 1000)
    return out
