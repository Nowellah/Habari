from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from core import sla
from core.harm import picks
from core.messages import status_words
from core.models import Case, Notification

STAFF_GROUPS = {"officer", "supervisor", "safeguarding", "admin"}
SUPERVISOR_GROUPS = {"supervisor", "admin"}


@never_cache  # nothing about the chat stays in the browser cache
def chat_page(request):
    return render(request, "dashboard/chat.html", {"helpline": settings.HELPLINE_NUMBER})


def status_page(request, code):
    case = get_object_or_404(Case, code__iexact=code)
    return render(request, "dashboard/status.html", {"words": status_words(case), "helpline": settings.HELPLINE_NUMBER})


def require_staff_role(user):
    if not (user.is_superuser or user.groups.filter(name__in=STAFF_GROUPS).exists()):
        raise PermissionDenied


def is_supervisor(user):
    return user.is_superuser or user.groups.filter(name__in=SUPERVISOR_GROUPS).exists()


def _notifications_for(user):
    if is_supervisor(user):
        return Notification.objects.filter(audience__in=["supervisor", "on_call"]).select_related("case")[:10]
    officer = getattr(user, "officer", None)
    if officer:
        return Notification.objects.filter(officer=officer).select_related("case")[:10]
    return []


@login_required
def officer_list(request):
    require_staff_role(request.user)
    labels = {k: p["short_en"] for k, p in picks().items()}
    cases = [
        {"case": c, "pick_label": labels.get(c.pick, "-"), "clock": sla.clock_state(c)}
        for c in Case.objects.select_related("assigned_officer__user").order_by("-severity", "created_at")[:200]
    ]
    return render(request, "dashboard/officer_list.html",
                  {"cases": cases, "notifications": _notifications_for(request.user)})
