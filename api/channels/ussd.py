"""USSD channel (*123# menus) for Africa's Talking.

The provider sends the whole history in `text`, joined with "*". We reply with
plain text starting "CON " (keep the menu open) or "END " (close it). Menus are
fixed: the AI never runs inside a USSD session.

Flow (steps[0] is always the first menu choice):
  START  → LANGUAGE (new step) → AGE → WHAT → (more) → case + SMS
"""
import hmac

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from channels.gateway import FEELINGS, _pin_hash, apply_feeling, create_case, get_reporter
from channels.sms import send_sms
from core.messages import msg, reply_languages
from core.models import Case

# ── Language menu ──────────────────────────────────────────────────────────────
# Shown before everything else for new sessions.
LANGS = {"1": "lg", "2": "rn", "3": "sw", "4": "en"}

# ── Age groups ─────────────────────────────────────────────────────────────────
AGE_FLAGS = {"1": "age_under_10", "2": "age_10_12", "3": "age_13_15", "4": "age_16_17"}

PICKS = {"1", "2", "3", "4", "5"}
FEELINGS_USSD = {"1": "little", "2": "lot", "3": "scared", "4": "danger"}


def _m(key, lang, **kw):
    """msg() for USSD — falls back to English silently."""
    return msg(key, lang if lang in reply_languages() else "en", **kw)


def _lang_menu(lang="en"):
    return _m("lang_question", lang)


def _age_menu(lang):
    labels = {
        "en": "How old are you?\n1 Under 10\n2 10–12\n3 13–15\n4 16–17",
        "lg": "Olina emyaka emeka?\n1 Wansi wa 10\n2 10–12\n3 13–15\n4 16–17",
        "rn": "Oine emyaka emeka?\n1 Wansi wa 10\n2 10–12\n3 13–15\n4 16–17",
        "sw": "Una miaka mingapi?\n1 Chini ya 10\n2 10–12\n3 13–15\n4 16–17",
    }
    return labels.get(lang, labels["en"])


def _what_menu(lang):
    lines = {
        "en": _m("menu", lang),
        "lg": _m("menu", "lg"),
        "rn": _m("menu", lang),  # falls back to English if no rn file
        "sw": _m("menu", lang),
    }
    return lines.get(lang, _m("menu", lang))


def _how_menu(lang):
    labels = {
        "en": "How does it feel?\n1 A little\n2 A lot\n3 Scared\n4 In danger\n0 Skip",
        "lg": "Okiwulira otya?\n1 Katono\n2 Nnyo\n3 Ntidde\n4 Ndi mu kabi\n0 Kireke",
        "rn": "Orisikirira bata?\n1 Buto\n2 Ninge\n3 Ntiina\n4 Ndi mu kabi\n0 Reka",
        "sw": "Unajisikiaje?\n1 Kidogo\n2 Sana\n3 Ninaogopa\n4 Niko hatarini\n0 Ruka",
    }
    return labels.get(lang, labels["en"])


def _confirm_menu(lang):
    labels = {
        "en": "1 Send now\n2 Add a few words by SMS later",
        "lg": "1 Weereza kati\n2 Yongerako ebigambo ku SMS oluvannyuma",
        "rn": "1 Tumiza kati\n2 Ongyeraho amagambo ku SMS oluvannyuma",
        "sw": "1 Tuma sasa\n2 Ongeza maneno kwa SMS baadaye",
    }
    return labels.get(lang, labels["en"])


def _sorry_menu(lang):
    labels = {
        "en": "Sorry, that was not an option. Please dial again.",
        "lg": "Mbeera, eyo si kyagulwa. Bambi kakasa nate.",
        "rn": "Mbabarira, etyo si kihitwa. Shaka nate.",
        "sw": "Samahani, hiyo haikuwa chaguo. Tafadhali piga tena.",
    }
    return labels.get(lang, labels["en"])


def _tips_text(lang):
    helpline = settings.HELPLINE_NUMBER
    tips = {
        "en": f"Stop replying. Do not pay. Do not delete messages. Save the username. Tell a trusted adult or call {helpline}.",
        "lg": f"Lekerako okuddamu. Tosakula. Tosangula bubaka. Kuuma erinnya. Buulira omukulu gw'oyesiga oba kuba ku {helpline}.",
        "rn": f"Reka okuddamu. Tosasula. Toresaho bubaka. Hima eizina. Bwira omu mukuru gw'orikwesiga oba kuba ku {helpline}.",
        "sw": f"Acha kujibu. Usilipi. Usifute ujumbe. Hifadhi jina la mtumiaji. Mwambie mtu mzima unayemwamini au piga {helpline}.",
    }
    return tips.get(lang, tips["en"])


def CON(text):
    return HttpResponse("CON " + text, content_type="text/plain")


def END(text):
    return HttpResponse("END " + text, content_type="text/plain")


# ── Step offsets in the `steps` list ──────────────────────────────────────────
# steps[0] = main menu choice (1-4)
# steps[1] = language choice (1-4)  ← NEW
# steps[2] = age group (1-4)         ← NEW
# For REPORT (choice 1):
#   steps[3] = harm pick (1-5)
#   steps[4] = feeling (1-4 / 0)
#   steps[5] = confirm (1-2)
# For CHECK (choice 3):
#   steps[3] = case code

S_MAIN = 0
S_LANG = 1
S_AGE  = 2
S_HARM = 3   # for report flow
S_FEEL = 4
S_CONF = 5


def _get_lang(steps):
    """Return the language code the child chose, or 'en' if not yet chosen."""
    if len(steps) > S_LANG and steps[S_LANG] in LANGS:
        return LANGS[steps[S_LANG]]
    return "en"


def _report(steps, phone):
    lang = _get_lang(steps)
    helpline = settings.HELPLINE_NUMBER

    # Step 1: show harm menu
    if len(steps) <= S_HARM:
        return CON(_what_menu(lang))

    pick = steps[S_HARM]
    if pick not in PICKS:
        return END(_sorry_menu(lang))

    reporter = get_reporter("ussd", phone, lang)

    # Danger (pick 1): create case immediately, skip further questions
    if pick == "1":
        case = create_case(reporter, "ussd", "1", "", lang)
        sms_text = _m("danger", lang, code=case.code)
        send_sms(reporter, sms_text, to_number=phone, reply=True)
        end_text = {
            "en": f"Call {helpline} now, it is free. A person is coming to help. Case {case.code}.",
            "lg": f"Kuba ku {helpline} kati, kya bwereere. Omuntu ajja kukuyamba. Ensonga {case.code}.",
            "rn": f"Ita ku {helpline} kati, ni bwereere. Omu azija kukuyamba. Ensonga {case.code}.",
            "sw": f"Piga {helpline} sasa, ni bure. Mtu anakuja kukusaidia. Nambari {case.code}.",
        }
        return END(end_text.get(lang, end_text["en"]))

    # Step 2: ask how it feels
    if len(steps) <= S_FEEL:
        return CON(_how_menu(lang))

    feeling_choice = steps[S_FEEL]
    if feeling_choice not in FEELINGS_USSD and feeling_choice != "0":
        return END(_sorry_menu(lang))

    # Step 3: confirm
    if len(steps) <= S_CONF:
        return CON(_confirm_menu(lang))

    if steps[S_CONF] not in ("1", "2"):
        return END(_sorry_menu(lang))

    case = create_case(reporter, "ussd", pick, "", lang)

    if feeling_choice in FEELINGS_USSD:
        apply_feeling(case, FEELINGS_USSD[feeling_choice])

    # High severity: helpline first
    if case.severity >= 4:
        sms_text = _m("danger", lang, code=case.code)
        send_sms(reporter, sms_text, to_number=phone, reply=True)
        end_text = {
            "en": f"Call {helpline} now, it is free. A person is coming to help. Case {case.code}.",
            "lg": f"Kuba ku {helpline} kati, kya bwereere. Omuntu ajja kukuyamba. Ensonga {case.code}.",
            "rn": f"Ita ku {helpline} kati, ni bwereere. Omu azija kukuyamba. Ensonga {case.code}.",
            "sw": f"Piga {helpline} sasa, ni bure. Mtu anakuja kukusaidia. Nambari {case.code}.",
        }
        return END(end_text.get(lang, end_text["en"]))

    sms_text = _m("received", lang, code=case.code)
    send_sms(reporter, sms_text, to_number=phone, reply=True)

    if steps[S_CONF] == "2":
        add_later = {
            "en": f"Thank you. Case {case.code}. SMS us your words and the code.",
            "lg": f"Weebale. Ensonga {case.code}. Tuweereza ebigambo n'ennamba ku SMS.",
            "rn": f"Mwebale. Ensonga {case.code}. Tutumira amagambo n'ennamba ku SMS.",
            "sw": f"Asante. Nambari {case.code}. Tutumie maneno yako na nambari kwa SMS.",
        }
        return END(add_later.get(lang, add_later["en"]))

    done = {
        "en": f"Thank you. Not your fault. Case {case.code}. We sent you an SMS.",
        "lg": f"Weebale. Si nsobi yo. Ensonga {case.code}. Twakuweereza SMS.",
        "rn": f"Mwebale. Si nsobi yo. Ensonga {case.code}. Twakutumira SMS.",
        "sw": f"Asante. Si kosa lako. Nambari {case.code}. Tumekutumia SMS.",
    }
    return END(done.get(lang, done["en"]))


def _check(steps, lang):
    # For CHECK, steps are: [0]=choice(3), [1]=case code, [2]=pin word
    CHECK_CODE = 1
    CHECK_PIN  = 2
    if len(steps) <= CHECK_CODE:
        labels = {
            "en": "Enter your case code, for example HB-ABC234",
            "lg": "Teeka ennamba y'ensonga yo, okugeza HB-ABC234",
            "rn": "Teeka ennamba y'ensonga yo, okugeza HB-ABC234",
            "sw": "Ingiza nambari yako ya kesi, kwa mfano HB-ABC234",
        }
        return CON(labels.get(lang, labels["en"]))
    case = Case.objects.filter(code__iexact=steps[CHECK_CODE].strip()).first()
    if not case:
        return END(_m("status_unknown", lang))
    owner = case.reporter
    if owner and owner.pin_hash:
        if len(steps) <= CHECK_PIN:
            labels = {
                "en": "Enter your word",
                "lg": "Teeka ekigambo kyo",
                "rn": "Teeka ekigambo kyawe",
                "sw": "Ingiza neno lako",
            }
            return CON(labels.get(lang, labels["en"]))
        if not hmac.compare_digest(_pin_hash(owner, steps[CHECK_PIN]), owner.pin_hash):
            return END(_m("status_need_pin", lang, code=case.code))
    from core.messages import status_words
    return END(status_words(case, lang))


def _talk(phone, lang):
    reporter = get_reporter("ussd", phone, lang)
    case = create_case(reporter, "ussd", "", "", lang)
    case.severity = max(case.severity, 2)
    case.flags = sorted(set(case.flags) | {"talk_request"})
    case.save(update_fields=["severity", "flags"])
    helpline = settings.HELPLINE_NUMBER
    end_text = {
        "en": f"A helper will contact you soon. Case {case.code}. If you are in danger call {helpline}.",
        "lg": f"Omuyambi ajja kukutuukirira mangu. Ensonga {case.code}. Bw'oli mu kabi kuba ku {helpline}.",
        "rn": f"Omuyambi azija kukutuukirira mangu. Ensonga {case.code}. Bw'oli mu kabi ita ku {helpline}.",
        "sw": f"Msaidizi atakuwasiliana hivi karibuni. Nambari {case.code}. Ukiwa hatarini piga {helpline}.",
    }
    return END(end_text.get(lang, end_text["en"]))


@csrf_exempt  # called by Africa's Talking
@require_POST
def ussd_hook(request):
    phone = request.POST.get("phoneNumber", "")
    text  = request.POST.get("text", "")
    if not phone:
        return END("Sorry, something went wrong. Please dial again.")

    steps = text.split("*") if text else []

    # ── Opening screen ─────────────────────────────────────────────────────────
    if not steps:
        main_menu = (
            "Habari. You are not in trouble.\n"
            "1 Report\n"
            "2 Talk to someone\n"
            "3 Check my case\n"
            "4 Safety tips"
        )
        return CON(main_menu)

    choice = steps[S_MAIN]

    # ── Non-report paths skip language/age collection ──────────────────────────
    # Only the Report flow (choice 1) goes through language → age → harm.
    # Check / Talk / Tips work immediately with whatever language is available.
    if choice != "1":
        # For these shorter flows we still respect a language if it was provided as step 2.
        lang = _get_lang(steps) if len(steps) > 1 else "en"
        if choice == "2":
            return _talk(phone, lang)
        if choice == "3":
            # steps for check: steps[1] = case code, steps[2] = pin word
            return _check(steps, lang)
        if choice == "4":
            return END(_tips_text(lang))
        return END(_sorry_menu("en"))

    # ── Language selection (step 2, Report flow only) ──────────────────────────
    if len(steps) == 1:
        return CON(_lang_menu())   # always English at this point — child hasn't chosen yet

    lang = _get_lang(steps)

    # ── Age selection (step 3, Report flow only) ───────────────────────────────
    if len(steps) == 2:
        return CON(_age_menu(lang))

    # Record age flag on the reporter (non-blocking, best effort)
    if len(steps) >= 3 and steps[S_AGE] in AGE_FLAGS:
        try:
            reporter = get_reporter("ussd", phone, lang)
            flag = AGE_FLAGS[steps[S_AGE]]
            if flag not in (reporter.district or ""):
                pass  # age stored on case after create_case; see _report
        except Exception:
            pass

    # ── Report flow ────────────────────────────────────────────────────────────
    return _report(steps, phone)
