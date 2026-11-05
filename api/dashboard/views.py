from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.static import serve

from core import ai_client, sla
from core.harm import picks
from core.messages import status_words
from core.models import Case, Notification

STAFF_GROUPS = {"officer", "supervisor", "safeguarding", "admin"}
SUPERVISOR_GROUPS = {"supervisor", "admin"}


def web_app_index():
    """The built React app's page, or None when it has not been built."""
    dist = settings.WEB_DIST
    index = dist / "index.html" if dist else None
    return index if index and index.is_file() else None


@never_cache  # nothing about the chat stays in the browser cache
def chat_page(request):
    index = web_app_index()
    if index:
        return HttpResponse(index.read_text(encoding="utf8"), content_type="text/html; charset=utf-8")
    return render(request, "dashboard/chat.html", {"helpline": settings.HELPLINE_NUMBER})


@never_cache
def spa_page(request):
    """Any screen of the React app. Without a build there is only the chat page to show."""
    index = web_app_index()
    if index:
        return HttpResponse(index.read_text(encoding="utf8"), content_type="text/html; charset=utf-8")
    return redirect("/chat")


def web_asset(request, path):
    """Hashed files of the built React app."""
    if not settings.WEB_DIST:
        raise Http404
    return serve(request, path, document_root=settings.WEB_DIST / "assets")


@never_cache
def app_config(request):
    """Settings the web app needs before it can show the helpline."""
    return JsonResponse({"helpline": settings.HELPLINE_NUMBER, "voice": ai_client.voice_available()})


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


def metrics_page(request):
    """Evaluation results for judges and partners. Synthetic data only, so it is public."""
    import json

    path = settings.EVAL_RESULTS_DIR / "metrics.json"
    data = json.loads(path.read_text(encoding="utf8")) if path.exists() else None
    sets = []
    if data:
        for key, title in (("hard_test_v2", "Hard test set 2 (written before the v0.3 rules)"),
                           ("hard_test", "Hard test set 1 (used to write the v0.3 rules)"),
                           ("synthetic_test", "Synthetic test set")):
            s = data.get(key)
            if not s:
                continue
            labels = s["confusion"]["labels"]
            rows = [(labels[i], row) for i, row in enumerate(s["confusion"]["matrix"]) if any(row)]
            used = [j for j in range(len(labels)) if any(r[j] for _, r in rows)]
            sets.append({"title": title, "s": s, "cm_labels": [labels[j] for j in used],
                         "cm_rows": [(name, [row[j] for j in used]) for name, row in rows]})
    return render(request, "dashboard/metrics.html", {"data": data, "sets": sets})


def feature_status(request):
    """Every feature with an honest label: Built, Simulated or Planned."""
    import json

    data = json.loads((settings.SHARED_DIR / "feature_status.json").read_text(encoding="utf8"))
    counts = {s: sum(1 for f in data["features"] if f["status"] == s) for s in ("Built", "Simulated", "Planned")}
    return render(request, "dashboard/feature_status.html", {"data": data, "counts": counts})
