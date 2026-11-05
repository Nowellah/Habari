from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render

from core.harm import picks
from core.messages import status_words
from core.models import Case

STAFF_GROUPS = {"officer", "supervisor", "safeguarding", "admin"}


def status_page(request, code):
    case = get_object_or_404(Case, code__iexact=code)
    return render(request, "dashboard/status.html", {"words": status_words(case), "helpline": settings.HELPLINE_NUMBER})


def _require_staff_role(user):
    if not (user.is_superuser or user.groups.filter(name__in=STAFF_GROUPS).exists()):
        raise PermissionDenied


@login_required
def officer_list(request):
    _require_staff_role(request.user)
    labels = {k: p["short_en"] for k, p in picks().items()}
    cases = [
        {"case": c, "pick_label": labels.get(c.pick, "-")}
        for c in Case.objects.order_by("-severity", "created_at")[:200]
    ]
    return render(request, "dashboard/officer_list.html", {"cases": cases})
