"""Officer case page, case actions and the partner board."""
from statistics import median

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core import allocation, followup, router, sla
from core.harm import picks
from core.messages import _messages
from core.models import Case, Officer, Partner
from dashboard.views import is_supervisor, require_staff_role

CLOSE_REASONS = {
    "resolved": Case.Status.CLOSED,
    "referred_accepted": Case.Status.CLOSED,
    "unfounded": Case.Status.CLOSED_UNFOUNDED,
    "child_asked_to_stop": Case.Status.CLOSED_CHILD_STOP,
}
OFFICER_STATUSES = {"in_progress": Case.Status.IN_PROGRESS, "resolved": Case.Status.RESOLVED}


def _case(request, code):
    require_staff_role(request.user)
    return get_object_or_404(Case.objects.select_related("assigned_officer__user"), code__iexact=code)


def _replies():
    return {k: v.format(helpline=settings.HELPLINE_NUMBER) for k, v in _messages("en")["replies"].items()}


@login_required
def case_detail(request, code):
    case = _case(request, code)
    planned, note = router.plan_routes(case)
    return render(request, "dashboard/officer_case.html", {
        "case": case,
        "pick": picks().get(case.pick),
        "clock": sla.clock_state(case),
        "planned": planned,
        "route_note": case.routing_note or note,
        "referrals": case.referrals.select_related("partner").order_by("sent_at"),
        "events": case.sla_events.order_by("at"),
        "messages": case.messages.order_by("created_at"),
        "replies": _replies(),
        "close_reasons": CLOSE_REASONS,
        "officers": Officer.objects.select_related("user").order_by("user__username"),
        "supervisor": is_supervisor(request.user),
    })


@login_required
@require_POST
def case_ack(request, code):
    case = _case(request, code)
    if not case.ack_at:
        case.ack_at = timezone.now()
        case.save(update_fields=["ack_at"])
        sla.once(case, "acknowledged", f"by {request.user.get_username()}")
    return redirect("case_detail", code=case.code)


@login_required
@require_POST
def case_reply(request, code):
    case = _case(request, code)
    text = _replies().get(request.POST.get("template", ""))
    if text is None:  # only reviewed replies reach a child
        return HttpResponseBadRequest("Choose one of the reviewed replies.")
    followup.send_to_child(case, text)
    now = timezone.now()
    case.ack_at = case.ack_at or now
    case.first_response_at = case.first_response_at or now
    if case.status in (Case.Status.RECEIVED, Case.Status.TRIAGED, Case.Status.ASSIGNED):
        case.status = Case.Status.IN_PROGRESS
    case.save(update_fields=["ack_at", "first_response_at", "status"])
    sla.once(case, "first_response", f"reply '{request.POST['template']}' by {request.user.get_username()}")
    return redirect("case_detail", code=case.code)


@login_required
@require_POST
def case_refer(request, code):
    case = _case(request, code)
    router.send_referrals(case)
    if case.status not in followup.CLOSED:
        followup.set_status(case, Case.Status.REFERRED)
    return redirect("case_detail", code=case.code)


@login_required
@require_POST
def case_status(request, code):
    case = _case(request, code)
    new = OFFICER_STATUSES.get(request.POST.get("status", ""))
    if new is None:
        return HttpResponseBadRequest("Unknown status.")
    followup.set_status(case, new)
    return redirect("case_detail", code=case.code)


@login_required
@require_POST
def case_close(request, code):
    case = _case(request, code)
    reason = request.POST.get("reason", "")
    if reason not in CLOSE_REASONS:
        return HttpResponseBadRequest("A case can only be closed with a reason.")
    note = request.POST.get("note", "").strip()[:150]
    followup.set_status(case, CLOSE_REASONS[reason],
                        reason=f"{reason} by {request.user.get_username()}" + (f": {note}" if note else ""))
    return redirect("case_detail", code=case.code)


@login_required
@require_POST
def case_reassign(request, code):
    case = _case(request, code)
    if not is_supervisor(request.user):
        raise PermissionDenied
    officer = get_object_or_404(Officer, pk=request.POST.get("officer"))
    allocation.assign_by_supervisor(case, officer, request.user.get_username())
    return redirect("case_detail", code=case.code)


@login_required
def partner_board(request):
    require_staff_role(request.user)
    now = timezone.now()
    scale = sla.scale()
    rows = []
    for p in Partner.objects.order_by("name"):
        refs = list(p.referral_set.all())
        window_s = p.ack_minutes * 60 / scale
        acked = [(r.ack_at - r.sent_at).total_seconds() for r in refs if r.ack_at]
        decided = [r for r in refs if r.ack_at or (now - r.sent_at).total_seconds() > window_s]
        breached = [r for r in decided if ((r.ack_at or now) - r.sent_at).total_seconds() > window_s]
        rows.append({
            "partner": p,
            "sent": len(refs),
            "acked": len(acked),
            "median_sla_min": round(median(acked) / 60 * scale) if acked else None,
            "breach_pct": round(100 * len(breached) / len(decided)) if decided else None,
            "window": p.ack_minutes,
        })
    return render(request, "dashboard/partners.html", {"rows": rows})
