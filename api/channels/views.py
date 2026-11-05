import json

from django.http import Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from channels.gateway import handle
from core.models import CHANNELS

CHANNEL_NAMES = {c for c, _ in CHANNELS}


@csrf_exempt  # called by channel adapters and providers, not browser forms
@require_POST
def channel_api(request, name):
    if name not in CHANNEL_NAMES:
        raise Http404("unknown channel")
    try:
        body = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid JSON"}, status=400)
    if not isinstance(body, dict) or not body.get("sender_id"):
        return JsonResponse({"error": "sender_id is required"}, status=400)
    out = handle(
        channel=name,
        sender_id=body["sender_id"],
        text=body.get("text") or "",
        language=body.get("language"),
        attachments=body.get("attachments"),
        location=body.get("location"),
        meta=body.get("meta"),
    )
    return JsonResponse(out)
