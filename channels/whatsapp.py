"""WhatsApp Cloud API adapter (Meta). Status: Simulated until a test number is set up.

Setup (plan §9.8): create a Meta developer app with WhatsApp, then set in .env:
  WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_VERIFY_TOKEN, WHATSAPP_APP_SECRET
and point the webhook at PUBLIC_BASE_URL/hooks/whatsapp (subscribe to "messages").
Without a token, replies are kept in the outbox (provider "whatsapp-simulator").
"""
import hashlib
import hmac
import json
import logging

import requests
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from channels.gateway import handle
from core.messages import msg
from core.models import OutboundSMS, Reporter
from core.utils import pseudo_id

log = logging.getLogger(__name__)


def _graph_url():
    return f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_ID}/messages"


def send_whatsapp(reporter, wa_id, text):
    """Send one text message, or keep it in the simulator outbox when no token is set."""
    if settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_ID and wa_id:
        try:
            r = requests.post(_graph_url(), timeout=10,
                              headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"},
                              json={"messaging_product": "whatsapp", "to": wa_id, "type": "text",
                                    "text": {"body": text[:4096]}})
            status = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            status = f"failed: {type(e).__name__}"
        OutboundSMS.objects.create(reporter=reporter, text=text, provider="whatsapp", provider_status=status)
        return
    OutboundSMS.objects.create(reporter=reporter, text=text, provider="whatsapp-simulator")


def _reporter(wa_id):
    return Reporter.objects.filter(pseudo_id=pseudo_id("whatsapp", "+" + wa_id, settings.HMAC_SECRET)).first()


def _signature_ok(request):
    secret = settings.WHATSAPP_APP_SECRET
    if not secret:
        return True  # local simulation; set WHATSAPP_APP_SECRET before going live
    sent = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sent, expected)


def _handle_message(m):
    wa_id = m.get("from", "")
    sender = "+" + wa_id
    kind = m.get("type")
    if kind == "text":
        out = handle(channel="whatsapp", sender_id=sender, text=m["text"].get("body", ""))
    elif kind == "interactive":
        reply = m["interactive"].get("button_reply") or m["interactive"].get("list_reply") or {}
        out = handle(channel="whatsapp", sender_id=sender, text=reply.get("id", ""))
    elif kind == "location":
        loc = m["location"]
        out = handle(channel="whatsapp", sender_id=sender, text="",
                     location={"lat": loc.get("latitude"), "lon": loc.get("longitude")})
    else:  # audio, image, sticker...: voice over WhatsApp is Planned
        handle(channel="whatsapp", sender_id=sender, text="")  # registers the child, no reply text needed
        send_whatsapp(_reporter(wa_id), wa_id, msg("voice_failed").replace("/start", "HELP"))
        return
    send_whatsapp(_reporter(wa_id), wa_id, out["reply_text"])


@csrf_exempt  # called by Meta
def whatsapp_hook(request):
    if request.method == "GET":
        ok = (request.GET.get("hub.mode") == "subscribe" and settings.WHATSAPP_VERIFY_TOKEN
              and hmac.compare_digest(request.GET.get("hub.verify_token", ""), settings.WHATSAPP_VERIFY_TOKEN))
        return HttpResponse(request.GET.get("hub.challenge", "")) if ok else HttpResponseForbidden()
    if request.method != "POST":
        return HttpResponse(status=405)
    if not _signature_ok(request):
        return HttpResponseForbidden("bad signature")
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return HttpResponse(status=400)
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            for m in change.get("value", {}).get("messages", []):  # "statuses" updates are ignored
                try:
                    _handle_message(m)
                except Exception:
                    log.exception("whatsapp message failed")
    return HttpResponse("OK")  # always 200 so Meta does not retry and duplicate messages
