"""USSD channel (*123# menus) for Africa's Talking.

The provider sends the whole history in `text`, joined with "*". We reply with
plain text starting "CON " (keep the menu open) or "END " (close it). Menus are
fixed: the AI never runs inside a USSD session.
"""
import hmac

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from channels.gateway import FEELINGS, _pin_hash, apply_feeling, create_case, get_reporter
from channels.sms import send_sms
from core.messages import msg, status_words
from core.models import Case

LANGS = {"1": "lg", "2": "rn", "3": "sw", "4": "en"}
PICKS = {"1", "2", "3", "4", "5"}

MAIN = "Habari. You are not in trouble.\n1 Report\n2 Talk to someone\n3 Check my case\n4 Safety tips"
WHAT = "What happened?\n1 Danger/self-harm\n2 Asked for pics/money\n3 Adult hurting me\n4 Mean or fake\n5 Upsetting online"
LANGUAGE = "Language?\n1 Luganda 2 Runyankore\n3 Swahili 4 English"
HOW = "How does it feel?\n1 A little\n2 A lot\n3 Scared\n4 In danger\n0 Skip"
CONFIRM = "1 Send now\n2 Add a few words by SMS later"
SORRY = "Sorry, that was not an option. Please dial again."
TIPS = "Stop replying. Do not pay. Do not delete messages. Save the username. Tell a trusted adult or call {helpline}."


def CON(text):
    return HttpResponse("CON " + text, content_type="text/plain")


def END(text):
    return HttpResponse("END " + text, content_type="text/plain")


def _report(steps, phone):
    if len(steps) == 1:
        return CON(WHAT)
    pick = steps[1]
    if pick not in PICKS:
        return END(SORRY)
    reporter = get_reporter("ussd", phone, None)
    helpline = settings.HELPLINE_NUMBER
    if pick == "1":
        # Danger: no more questions. Create the case now and show the helpline first.
        case = create_case(reporter, "ussd", "1", "", None)
        send_sms(reporter, f"Habari: case {case.code}. Call {helpline} now, free. A person is coming to help.",
                 to_number=phone, reply=True)
        return END(f"Call {helpline} now, it is free. A person is coming to help. Case {case.code}.")
    if len(steps) == 2:
        return CON(LANGUAGE)
    if steps[2] not in LANGS:
        return END(SORRY)
    if len(steps) == 3:
        return CON(HOW)
    if steps[3] not in FEELINGS and steps[3] != "0":
        return END(SORRY)
    if len(steps) == 4:
        return CON(CONFIRM)
    if steps[4] not in ("1", "2"):
        return END(SORRY)
    case = create_case(reporter, "ussd", pick, "", LANGS[steps[2]])
    if steps[3] in FEELINGS:
        apply_feeling(case, FEELINGS[steps[3]])
    if case.severity >= 4:  # the child said they are in danger: helpline first, as for pick 1
        send_sms(reporter, f"Habari: case {case.code}. Call {helpline} now, free. A person is coming to help.",
                 to_number=phone, reply=True)
        return END(f"Call {helpline} now, it is free. A person is coming to help. Case {case.code}.")
    send_sms(reporter, f"Habari: case {case.code}. A person will help. Text STATUS {case.code} to check.",
             to_number=phone, reply=True)
    if steps[4] == "2":
        return END(f"Thank you. Case {case.code}. SMS us your words and the code.")
    return END(f"Thank you. Not your fault. Case {case.code}. We sent you an SMS.")


def _check(steps):
    if len(steps) == 1:
        return CON("Enter your case code, for example HB-ABC234")
    case = Case.objects.filter(code__iexact=steps[1].strip()).first()
    if not case:
        return END(msg("status_unknown"))
    owner = case.reporter
    if owner and owner.pin_hash:
        if len(steps) == 2:
            return CON("Enter your word")
        if not hmac.compare_digest(_pin_hash(owner, steps[2]), owner.pin_hash):
            return END(msg("status_need_pin", code=case.code))
    return END(status_words(case))


def _talk(phone):
    reporter = get_reporter("ussd", phone, None)
    case = create_case(reporter, "ussd", "", "", None)
    case.severity = max(case.severity, 2)
    case.flags = sorted(set(case.flags) | {"talk_request"})
    case.save(update_fields=["severity", "flags"])
    return END(f"A helper will contact you soon. Case {case.code}. If you are in danger call {settings.HELPLINE_NUMBER}.")


@csrf_exempt  # called by Africa's Talking
@require_POST
def ussd_hook(request):
    phone = request.POST.get("phoneNumber", "")
    text = request.POST.get("text", "")
    if not phone:
        return END(SORRY)
    steps = text.split("*") if text else []
    if not steps:
        return CON(MAIN)
    choice = steps[0]
    if choice == "1":
        return _report(steps, phone)
    if choice == "2":
        return _talk(phone)
    if choice == "3":
        return _check(steps)
    if choice == "4":
        return END(TIPS.format(helpline=settings.HELPLINE_NUMBER))
    return END(SORRY)
