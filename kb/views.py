from django.http import Http404
from django.shortcuts import render
from django.utils.safestring import mark_safe

from dashboard.views import STAFF_GROUPS
from kb.library import PUBLIC, articles, render_markdown, search


def _audiences(user):
    staff = user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=STAFF_GROUPS).exists())
    return PUBLIC | {"officer"} if staff else PUBLIC


def kb_list(request):
    q = request.GET.get("q", "").strip()[:100]
    return render(request, "kb/list.html", {"q": q, "results": search(q, _audiences(request.user))})


def kb_article(request, slug):
    article = next((a for a in articles() if a["slug"] == slug), None)
    if article is None or article["audience"] not in _audiences(request.user):
        raise Http404
    return render(request, "kb/article.html", {"a": article, "body": mark_safe(render_markdown(article["body"]))})
