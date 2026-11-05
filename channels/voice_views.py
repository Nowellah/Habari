"""Voice notes from the web chat: audio in, words back for the child to check.

Nothing is reported here. The child sees the words, can fix them, and sends
them like any typed message.
"""
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core import ai_client

MAX_AUDIO = 10 * 1024 * 1024
TYPE_INSTEAD = "We could not turn your voice into words. Please type instead."


@csrf_exempt  # the anonymous chat page sets no cookies, so it has no CSRF token
@require_POST
def voice_transcribe(request):
    audio = request.FILES.get("audio")
    if audio is None or audio.size == 0:
        return JsonResponse({"message": "No voice note was received."}, status=400)
    if audio.size > MAX_AUDIO:
        return JsonResponse({"message": "That voice note is too long. Please keep it short."}, status=413)
    out = ai_client.transcribe(audio.read(), audio.name, request.POST.get("language") or None)
    if out is None:
        return JsonResponse({"message": TYPE_INSTEAD}, status=503)
    return JsonResponse({"text": out["text"], "language": out.get("language", "unknown")})


def voice_shortcut(request):
    """Home-screen shortcut target: the chat page, ready to speak."""
    return redirect("/chat?voice=1")
