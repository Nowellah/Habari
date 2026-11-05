"""Phone simulators for demos and testing. Switched off when SIMULATORS_ENABLED is off."""
from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import render

from channels.sms import reporter_for_number


def _require_enabled():
    if not settings.SIMULATORS_ENABLED:
        raise Http404


def sim_sms(request):
    _require_enabled()
    return render(request, "channels/sim_sms.html")


def sim_ussd(request):
    _require_enabled()
    return render(request, "channels/sim_ussd.html")


def sim_sms_outbox(request):
    """SMS messages sent to one simulated phone number."""
    _require_enabled()
    reporter = reporter_for_number(request.GET.get("number", ""))
    rows = reporter.outbound_sms.order_by("id") if reporter else []
    return JsonResponse({"messages": [{"id": r.id, "text": r.text} for r in rows]})
