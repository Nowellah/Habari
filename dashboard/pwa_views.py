"""Installable web app: manifest, service worker, share-to-Habari and the embeddable report link."""
import re
from urllib.parse import urlencode

from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render

URL_IN_TEXT = re.compile(r"https?://[^\s<>\"']+")


def manifest(request):
    data = {
        "name": "Habari: I need a friend",
        "short_name": "Habari",
        "start_url": "/chat",
        "scope": "/",
        "display": "standalone",
        "background_color": "#fbfaf7",
        "theme_color": "#2f6f5e",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
        # Android: "Share" from TikTok, Instagram or X offers Habari. iOS web apps cannot do this.
        "share_target": {"action": "/share", "method": "GET",
                         "params": {"title": "title", "text": "text", "url": "url"}},
        "shortcuts": [
            {"name": "I need a friend", "url": "/chat?quick=1"},
            {"name": "Speak to Habari", "url": "/voice"},
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json")


SERVICE_WORKER = """// Habari service worker. It exists so the app can be installed and receive shares.
// It deliberately caches nothing, so no report or page is ever stored on the phone.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
"""


def service_worker(request):
    r = HttpResponse(SERVICE_WORKER, content_type="application/javascript")
    r["Cache-Control"] = "no-store"
    return r


def _web_url(value):
    value = (value or "").strip()
    return value if re.match(r"^https?://", value, re.I) else ""


def _to_chat(params):
    clean = {k: v[:500] for k, v in params.items() if v}
    return redirect("/chat?" + urlencode(clean))


def share(request):
    """Share target: what the child shared opens in the chat, ready to report."""
    text = request.GET.get("text", "")
    url = _web_url(request.GET.get("url")) or _web_url((URL_IN_TEXT.search(text) or [""])[0])
    return _to_chat({"shared": "1", "text": text, "title": request.GET.get("title", ""), "url": url})


def report_link(request):
    """Embeddable link a platform can add to its own report menu:
    /r?src=tiktok&handle=abc&url=https://..."""
    return _to_chat({"shared": "1", "src": re.sub(r"[^a-z0-9_]", "", request.GET.get("src", "").lower())[:20],
                     "handle": request.GET.get("handle", "")[:60], "url": _web_url(request.GET.get("url"))})


def mock_social(request):
    posts = [
        {"src": "tiktok", "handle": "dance_queen_ug", "text": "New dance challenge! Who is joining?",
         "url": "https://www.tiktok.com/@dance_queen_ug/video/1"},
        {"src": "instagram", "handle": "fake_promo_256", "text": "Send me a private photo and I will send you airtime",
         "url": "https://www.instagram.com/p/demo2"},
        {"src": "x", "handle": "class_gossip", "text": "Look at this ugly kid from S2 lol",
         "url": "https://x.com/class_gossip/status/3"},
    ]
    for p in posts:
        p["report"] = "/r?" + urlencode({"src": p["src"], "handle": "@" + p["handle"], "url": p["url"]})
    return render(request, "dashboard/mock_social.html", {"posts": posts})
