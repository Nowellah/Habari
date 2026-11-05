"""Officer case page, case actions and the partner board."""
import json
from statistics import median

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from channels import voice_notes
from core import allocation, followup, linking, router, sla
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
        "voice_notes": voice_notes.for_case(case),
        "replies": _replies(),
        "close_reasons": CLOSE_REASONS,
        "officers": Officer.objects.select_related("user").order_by("user__username"),
        "supervisor": is_supervisor(request.user),
        "links": linking.linked_cases(case),
    })


@login_required
def case_voice(request, code, evidence_id):
    """The child's original recording, for the officer on the case only."""
    case = _case(request, code)
    evidence = get_object_or_404(case.evidence, pk=evidence_id, kind=voice_notes.KIND)
    try:
        path = voice_notes.audio_path(json.loads(evidence.value)["file"])
        audio = open(path, "rb")
    except (ValueError, KeyError, OSError):
        raise Http404("recording not found")
    response = FileResponse(audio, content_type="audio/wav")
    response["Cache-Control"] = "private, no-store"
    return response


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


@login_required
def poll_list(request):
    from polls.models import Poll
    from polls.service import results

    require_staff_role(request.user)
    if request.method == "POST":
        question = request.POST.get("question", "").strip()[:160]
        options = [o.strip() for o in request.POST.get("options", "").split(",") if o.strip()][:5]
        if question and len(options) >= 2:
            Poll.objects.create(question=question, options=options)
        return redirect("poll_list")
    polls = [{"poll": p, "rows": results(p), "count": p.responses.count()} for p in Poll.objects.order_by("-created_at")]
    return render(request, "dashboard/polls.html", {"polls": polls, "minimum": settings.HEATMAP_MIN})


@login_required
@require_POST
def poll_send(request, poll_id):
    from polls.models import Poll
    from polls.service import send_poll

    require_staff_role(request.user)
    poll = get_object_or_404(Poll, pk=poll_id)
    send_poll(poll)
    return redirect("poll_list")


@login_required
def heat_map(request):
    require_staff_role(request.user)
    return render(request, "dashboard/map.html", {"minimum": settings.HEATMAP_MIN})


@login_required
def heat_map_data(request):
    """Report counts per district. Below HEATMAP_MIN the count is withheld. No individual points."""
    from django.db.models import Count
    from django.http import JsonResponse

    from core.geo import centre

    require_staff_role(request.user)
    rows = []
    for row in Case.objects.exclude(district="").values("district").annotate(n=Count("id")).order_by("district"):
        point = centre(row["district"])
        if point is None:
            continue
        shown = row["n"] >= settings.HEATMAP_MIN
        rows.append({"district": row["district"], "lat": point[0], "lon": point[1],
                     "count": row["n"] if shown else None})
    return JsonResponse({"minimum": settings.HEATMAP_MIN, "districts": rows})


@login_required
def call_list(request):
    from core.calls import SCRIPTS
    from core.models import CallSession

    require_staff_role(request.user)
    return render(request, "dashboard/calls.html", {
        "scripts": SCRIPTS, "sessions": CallSession.objects.select_related("case").order_by("-started_at")[:20]})


@login_required
@require_POST
def call_start(request):
    from core.calls import SCRIPTS, start_call

    require_staff_role(request.user)
    name = request.POST.get("script", "")
    if name not in SCRIPTS:
        return HttpResponseBadRequest("Unknown call script.")
    session = start_call(name)
    return redirect(f"/officer/calls/{session.id}/")


@login_required
def call_detail(request, session_id):
    from core.models import CallSession

    require_staff_role(request.user)
    session = get_object_or_404(CallSession.objects.select_related("case"), pk=session_id)
    return render(request, "dashboard/call_detail.html", {"session": session})


@login_required
def call_data(request, session_id):
    from django.http import JsonResponse

    from core.calls import reveal_due
    from core.models import CallSession

    require_staff_role(request.user)
    session = get_object_or_404(CallSession.objects.select_related("case"), pk=session_id)
    reveal_due(session)
    case = Case.objects.get(pk=session.case_id)
    segments = [{"start": s.start_s, "end": s.end_s, "text": s.text, "text_en": s.text_en, "flags": s.flags}
                for s in session.segments.filter(revealed_at__isnull=False).order_by("seq")]
    return JsonResponse({"case_code": case.code, "severity": case.severity, "flags": case.flags,
                         "segments": segments, "done": len(segments) == session.segments.count()})
