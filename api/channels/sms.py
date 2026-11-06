"""SMS channel: Africa's Talking webhook in, SMS out (simulator outbox or the real provider)."""
import requests
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from channels.gateway import handle
from core.models import OutboundSMS, Reporter, ReporterVault
from core.utils import pseudo_id


def _at_url():
    host = "api.sandbox.africastalking.com" if settings.AT_USERNAME == "sandbox" else "api.africastalking.com"
    return f"https://{host}/version1/messaging"


def send_sms(reporter, text, to_number=None, reply=False):
    """Send (or queue in the simulator outbox) one SMS.

    reply=True means the child just wrote to us, so we always answer.
    Proactive messages are skipped once the child has sent STOP.
    """
    if reporter is not None and reporter.opted_out and not reply:
        return None
    number = to_number
    if number is None and reporter is not None:
        vault = ReporterVault.objects.filter(reporter=reporter).first()
        number = vault.raw_contact if vault else None

    # Save first so the simulator outbox shows the reply immediately, before any
    # provider network call that could block for several seconds.
    row = OutboundSMS(reporter=reporter, text=text)
    row.save()

    if settings.AT_API_KEY and number:
        try:
            r = requests.post(
                _at_url(),
                data={"username": settings.AT_USERNAME, "to": number, "message": text},
                headers={"apiKey": settings.AT_API_KEY, "Accept": "application/json"},
                timeout=10,
            )
            row.provider, row.provider_status = "africastalking", f"HTTP {r.status_code}"
        except requests.RequestException as e:
            row.provider, row.provider_status = "africastalking", f"failed: {type(e).__name__}"
        row.save(update_fields=["provider", "provider_status"])

    return row


def reporter_for_number(number):
    return Reporter.objects.filter(pseudo_id=pseudo_id("sms", number, settings.HMAC_SECRET)).first()


@csrf_exempt  # called by Africa's Talking, not a browser form
@require_POST
def sms_hook(request):
    frm, text = request.POST.get("from"), request.POST.get("text")
    if not frm or text is None:
        return HttpResponseBadRequest("from and text are required")
    out = handle(channel="sms", sender_id=frm, text=text)
    send_sms(reporter_for_number(frm), out["reply_text"], to_number=frm, reply=True)
    return HttpResponse("OK")
