"""Case tracking for the web app: the child enters their code (and secret word, if they set one)."""
import hmac
import json

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from channels.gateway import _pin_hash
from core import tracking
from core.models import Case

MAX_WRONG_WORDS = 8
LOCK_SECONDS = 15 * 60


@csrf_exempt  # the anonymous app sets no cookies, so it has no CSRF token
@require_POST
def case_status(request):
    try:
        data = json.loads(request.body or "{}")
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    code = str(data.get("code") or "").strip().upper()[:12]
    word = str(data.get("word") or "").strip()[:60]
    case = Case.objects.filter(code__iexact=code).first() if code else None
    if case is None:
        return JsonResponse({"message": "We could not find that code. Please check it and try again."}, status=404)
    owner = case.reporter
    if owner and owner.pin_hash:
        key = f"track-wrong:{case.code}"
        if cache.get(key, 0) >= MAX_WRONG_WORDS:
            return JsonResponse({"needs_word": True, "message": "Too many tries. Please wait a few minutes."}, status=429)
        if not word:
            return JsonResponse({"needs_word": True, "message": "Please enter your secret word."}, status=403)
        if not hmac.compare_digest(_pin_hash(owner, word), owner.pin_hash):
            cache.set(key, cache.get(key, 0) + 1, LOCK_SECONDS)
            return JsonResponse({"needs_word": True, "message": "That secret word does not match."}, status=403)
    response = JsonResponse(tracking.track(case))
    response["Cache-Control"] = "no-store"
    return response
