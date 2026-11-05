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
import re
import time

from django.conf import settings
from django.db import IntegrityError, transaction

from ai_service.language import detect_language
from core import ai_triage, followup, sla
from core.harm import pick_severity, picks
from core.messages import msg, status_words
from core.models import Case, Conversation, Message, Reporter, ReporterVault
from core.triage_rules import apply_rules
from core.utils import PHONE_CHANNELS, new_case_code, normalise_msisdn, pseudo_id

MENU_WORDS = {"HELP", "MENU", "START", "/START", "HI", "HELLO"}
RATINGS = {"1": "good", "2": "ok", "3": "not_good", "😀": "good", "🙂": "good", "😐": "ok", "😞": "not_good"}
FEELINGS = {"1": "little", "2": "lot", "3": "scared", "4": "danger"}
# What the child says they feel is a floor: it can raise severity, never lower it.
FEELING_FLOOR = {"little": 1, "lot": 2, "scared": 3, "danger": 4}
FEELING_LABELS = {"1": "A little", "2": "A lot", "3": "Scared", "4": "In danger", "0": "Skip"}
LANG_OPTIONS = {"1": ("lg", "Luganda"), "2": ("rn", "Runyankore"), "3": ("sw", "Swahili"), "4": ("en", "English")}


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
    cut = re.search(r"\s*Reply\s+\d|\s[0-9]\s+[A-Z]", text)
    if cut:
        text = text[:cut.start()].rstrip()
    out = dict(out, reply_text=text)
    if out["state"] == "DESCRIBE":
        out["options"] = [{"key": "0", "label": "Skip"}]
    return out


def _menu_options():
    return [{"key": k, "label": p["short_en"]} for k, p in picks().items()]


def _feeling_options():
    return [{"key": k, "label": label} for k, label in FEELING_LABELS.items()]


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


def _answer_feeling(conv, text):
    """Handle the reply to the feeling question. None means it was more information instead."""
    conv.draft = {}
    conv.save()
    if text == "0":
        return _reply(msg("feeling_thanks"), "CASE_OPEN", conv.case)
    feeling = FEELINGS.get(text)
    if feeling is None:
        return None
    case = conv.case
    apply_feeling(case, feeling)
    if case.severity >= 4:
        return _reply(msg("danger", code=case.code), "CASE_OPEN", case)
    if feeling == "little" and case.severity >= 3:
        return _reply(msg("feeling_higher"), "CASE_OPEN", case)
    return _reply(msg("feeling_thanks"), "CASE_OPEN", case)


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


def _case_reply(case, conv, text="", language=None):
    if case.severity < 4 and _should_ask_language(case, text, case.reporter, language):
        conv.state, conv.case, conv.draft = "PICK_LANG", case, {}
        conv.save()
        options = [{"key": k, "label": name} for k, (_, name) in LANG_OPTIONS.items()]
        return _reply(msg("received", code=case.code) + " " + msg("lang_question"), "PICK_LANG", case, options)
    if case.severity >= 4:  # already in danger: no more questions
        conv.state, conv.case, conv.draft = "CASE_OPEN", case, {}
        conv.save()
        return _reply(msg("danger", code=case.code), "CASE_OPEN", case)
    conv.state, conv.case, conv.draft = "CASE_OPEN", case, {"awaiting": "feeling"}
    conv.save()
    return _reply(msg("received", code=case.code) + " " + msg("feeling_ask"), "CASE_OPEN", case, _feeling_options())


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
    return _reply(status_words(case), conv.state if conv else "START", case)


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

    # Only a lone "HELP" opens the menu; "help me, he wants..." is a description.
    if command in MENU_WORDS and len(words) == 1:
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
            conv.state, conv.draft = "CASE_OPEN", {"awaiting": "feeling"}
            conv.save()
            return _reply(msg("lang_saved", language=name) + " " + msg("feeling_ask"), "CASE_OPEN", case,
                          _feeling_options())
        conv.state = "CASE_OPEN"  # they wrote something else: treat it as more information
        conv.save()

    if conv.state == "CASE_OPEN" and conv.case and (conv.draft or {}).get("awaiting") == "feeling":
        answered = _answer_feeling(conv, text)
        if answered:
            return answered

    if conv.state == "CHECKIN" and conv.case:
        case = conv.case
        if text == "1":
            conv.state = "RATE"
            conv.save()
            return _reply(msg("checkin_rate"), "RATE", case,
                          [{"key": "1", "label": "Good"}, {"key": "2", "label": "OK"}, {"key": "3", "label": "Not good"}])
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
            return _reply(msg("danger", code=case.code), "CASE_OPEN", case)
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

    if danger:  # a danger phrase skips the menu, in START or PICK_HARM
        return _case_reply(create_case(reporter, channel, "1", text, language), conv)

    if conv.state in ("START", "PICK_HARM") and len(words) >= 3:
        # Someone who simply tells us what happened is not sent back to a menu.
        if apply_rules(text).flags:
            return _case_reply(create_case(reporter, channel, "5", text, language), conv, text, language)
        conv.state, conv.draft = "PICK_HARM", {"said": text}
        conv.save()
        return _reply(msg("menu_retry"), "PICK_HARM", options=_menu_options())

    return open_menu("menu_retry" if conv.state == "PICK_HARM" else "menu")


def handle(channel, sender_id, text="", language=None, attachments=None, location=None, meta=None) -> dict:
    """Single entry point for every channel adapter. Returns the gateway response contract."""
    started = time.perf_counter()
    with transaction.atomic():
        reporter = get_reporter(channel, str(sender_id), language)
        text = (text or "").strip()
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
        out = _route(channel, reporter, text, language)
        if channel == "web":
            out = _for_buttons(out)
        if out.get("case_code") and meta:
            from channels.meta_evidence import attach_meta
            attach_meta(Case.objects.get(code=out["case_code"]), meta)
    out["first_reply_ms"] = round((time.perf_counter() - started) * 1000)
    return out


def handle_voice_transcript(channel, sender_id, transcript, language=None) -> dict:
    """Show the child what we heard. Nothing is sent until they reply 1 (or type)."""
    started = time.perf_counter()
    with transaction.atomic():
        reporter = get_reporter(channel, str(sender_id), language)
        conv = reporter.conversations.filter(channel=channel).order_by("-updated_at").first()             or Conversation.objects.create(reporter=reporter, channel=channel)
        conv.draft = {"voice_text": transcript, "prev_state": conv.state, "prev_draft": conv.draft}
        conv.state = "VOICE_CONFIRM"
        conv.save()
        out = _reply(msg("voice_confirm", text=transcript), "VOICE_CONFIRM", conv.case,
                     [{"key": "1", "label": "Send it"}])
    out["first_reply_ms"] = round((time.perf_counter() - started) * 1000)
    return out
