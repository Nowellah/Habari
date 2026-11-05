"""Channel gateway: every channel turns its message into the same call here.

State machine per reporter and channel:
    START -> PICK_HARM -> DESCRIBE -> CASE_OPEN
Pick 1, or a danger phrase at any point, creates a severity 4 case at once and
the reply starts with the helpline.
Commands work in any state: HELP, STATUS <code> [word], STOP, PIN <word>.
"""
import hashlib
import hmac
import time

from django.conf import settings
from django.db import IntegrityError, transaction

from core.harm import pick_severity, picks
from core.messages import msg, status_words
from core.models import Case, Conversation, Message, Reporter, ReporterVault
from core.triage_rules import apply_rules
from core.utils import PHONE_CHANNELS, new_case_code, normalise_msisdn, pseudo_id

MENU_WORDS = {"HELP", "MENU", "START", "/START", "HI", "HELLO"}


def _reply(text, state, case=None, options=None):
    return {"reply_text": text, "options": options or [], "case_code": case.code if case else None, "state": state}


def _menu_options():
    return [{"key": k, "label": p["short_en"]} for k, p in picks().items()]


def _reporter(channel, sender_id, language):
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
    return rep


def _pin_hash(reporter, word):
    key = f"pin:{reporter.pseudo_id}:{word.strip().lower()}"
    return hmac.new(settings.HMAC_SECRET.encode(), key.encode(), hashlib.sha256).hexdigest()


def _create_case(reporter, channel, pick, text, language):
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
    return case


def _case_reply(case, conv):
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

    if command in MENU_WORDS:
        return open_menu()

    danger = apply_rules(text).severity >= 4

    if conv.state == "CASE_OPEN" and conv.case:
        case = conv.case
        Message.objects.create(case=case, direction="in", text=text, channel=channel)
        rules = apply_rules(text, case.pick)
        was = case.severity
        case.severity = max(case.severity, rules.severity)
        case.flags = sorted(set(case.flags) | set(rules.flags))
        if rules.role_hint and not case.alleged_role:
            case.alleged_role = rules.role_hint
        case.save()
        # Phase 3: a severity rise resets the SLA clock here.
        if case.severity >= 4 and was < 4:
            return _reply(msg("danger", code=case.code), "CASE_OPEN", case)
        return _reply(msg("added", code=case.code), "CASE_OPEN", case)

    if conv.state == "DESCRIBE":
        pick = conv.draft.get("pick")
        case = _create_case(reporter, channel, pick, "" if text == "0" else text, language)
        return _case_reply(case, conv)

    if conv.state == "PICK_HARM" and text in picks():
        if text == "1":
            return _case_reply(_create_case(reporter, channel, "1", "", language), conv)
        conv.state, conv.draft = "DESCRIBE", {"pick": text}
        conv.save()
        return _reply(msg("describe"), "DESCRIBE")

    if danger:  # a danger phrase skips the menu, in START or PICK_HARM
        return _case_reply(_create_case(reporter, channel, "1", text, language), conv)

    return open_menu("menu_retry" if conv.state == "PICK_HARM" else "menu")


def handle(channel, sender_id, text="", language=None, attachments=None, location=None, meta=None) -> dict:
    """Single entry point for every channel adapter. Returns the gateway response contract."""
    started = time.perf_counter()
    with transaction.atomic():
        reporter = _reporter(channel, str(sender_id), language)
        out = _route(channel, reporter, (text or "").strip(), language)
    out["first_reply_ms"] = round((time.perf_counter() - started) * 1000)
    return out
