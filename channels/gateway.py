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
LANG_OPTIONS = {"1": ("lg", "Luganda"), "2": ("rn", "Runyankore"), "3": ("sw", "Swahili"), "4": ("en", "English")}


def _reply(text, state, case=None, options=None):
    return {"reply_text": text, "options": options or [], "case_code": case.code if case else None, "state": state}


def _menu_options():
    return [{"key": k, "label": p["short_en"]} for k, p in picks().items()]


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
    conv.state, conv.case, conv.draft = "CASE_OPEN", case, {}
    conv.save()
    key = "danger" if case.severity >= 4 else "received"
    return _reply(msg(key, code=case.code), "CASE_OPEN", case)


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


def _route(channel, reporter, text, language):
    words = text.split()
    command = words[0].upper() if words else ""
    conv = reporter.conversations.filter(channel=channel).order_by("-updated_at").first()

    if command == "STATUS":
        return _status(reporter, conv, words[1:])
    if command == "STOP":
        return _stop(reporter)
    if command == "PIN":
        if len(words) < 2:
            return _reply(msg("pin_need_word"), conv.state if conv else "START")
        reporter.pin_hash = _pin_hash(reporter, words[1])
        reporter.save()
        return _reply(msg("pin_saved"), conv.state if conv else "START")

    if conv is None:
        conv = Conversation.objects.create(reporter=reporter, channel=channel)

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
            conv.state = "CASE_OPEN"
            conv.save()
            return _reply(msg("lang_saved", language=name), "CASE_OPEN", case)
        conv.state = "CASE_OPEN"  # they wrote something else: treat it as more information
        conv.save()

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
        if text == "1":
            return _case_reply(create_case(reporter, channel, "1", "", language), conv)
        conv.state, conv.draft = "DESCRIBE", {"pick": text}
        conv.save()
        return _reply(msg("describe"), "DESCRIBE")

    if danger:  # a danger phrase skips the menu, in START or PICK_HARM
        return _case_reply(create_case(reporter, channel, "1", text, language), conv)

    return open_menu("menu_retry" if conv.state == "PICK_HARM" else "menu")


def handle(channel, sender_id, text="", language=None, attachments=None, location=None, meta=None) -> dict:
    """Single entry point for every channel adapter. Returns the gateway response contract."""
    started = time.perf_counter()
    with transaction.atomic():
        reporter = get_reporter(channel, str(sender_id), language)
        out = _route(channel, reporter, (text or "").strip(), language)
    out["first_reply_ms"] = round((time.perf_counter() - started) * 1000)
    return out
