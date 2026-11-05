import hmac

from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import Referral
from core.router import acknowledge_referral


@csrf_exempt  # called by partner systems with their key, not by browsers
@require_POST
def referral_ack(request, referral_id):
    ref = get_object_or_404(Referral.objects.select_related("partner"), pk=referral_id)
    key = request.headers.get("X-Partner-Key", "")
    if not key or not hmac.compare_digest(key, ref.partner.api_key):
        return HttpResponseForbidden("bad partner key")
    acknowledge_referral(ref)
    return JsonResponse({"case_code": ref.case.code, "acknowledged": True})
