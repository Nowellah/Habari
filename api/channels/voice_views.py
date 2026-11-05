"""Voice notes from the web chat: audio in, words back for the child to check.

Nothing is reported here. The child sees the words, can fix them, and sends
them like any typed message.
"""
import json

from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from channels import voice_notes
from channels.gateway import handle
from core import ai_client

MAX_AUDIO = 10 * 1024 * 1024
SPOKEN_LANGUAGES = {"en", "lg", "rn", "sw"}
TYPE_INSTEAD = "We could not turn your voice into words. Please type instead."


@csrf_exempt  # the anonymous chat page sets no cookies, so it has no CSRF token
@require_POST
def voice_transcribe(request):
    audio = request.FILES.get("audio")
    if audio is None or audio.size == 0:
        return JsonResponse({"message": "No voice note was received."}, status=400)
    if audio.size > MAX_AUDIO:
        return JsonResponse({"message": "That voice note is too long. Please keep it short."}, status=413)
    language = request.POST.get("language")
    out = ai_client.transcribe(audio.read(), audio.name, language if language in SPOKEN_LANGUAGES else None)
    if out is None:
        return JsonResponse({"message": TYPE_INSTEAD}, status=503)
    return JsonResponse({"text": out["text"], "language": out.get("language", "unknown")})


UNHEARD = "[voice note, the words could not be made out]"


@csrf_exempt  # the anonymous chat page sets no cookies, so it has no CSRF token
@require_POST
def voice_note(request):
    """A voice note from the web chat. The bot understands it like a typed message and replies,
    and the original recording is kept for the officer."""
    sender = (request.POST.get("sender_id") or "").strip()
    audio = request.FILES.get("audio")
    if not sender or audio is None or audio.size == 0:
        return JsonResponse({"message": "No voice note was received."}, status=400)
    if audio.size > MAX_AUDIO:
        return JsonResponse({"message": "That voice note is too long. Please keep it short."}, status=413)
    data = audio.read()
    if not voice_notes.is_wav(data):
        return JsonResponse({"message": "That recording could not be read."}, status=400)
    try:
        meta = json.loads(request.POST.get("meta") or "{}")
    except ValueError:
        meta = {}
    spoken = request.POST.get("spoken")
    heard = ai_client.transcribe(data, "voice.wav", spoken if spoken in SPOKEN_LANGUAGES else None)
    text = ((heard or {}).get("text") or "").strip() or UNHEARD
    note = voice_notes.save(data, voice_notes.clean_cues(_json(request.POST.get("cues"))))
    try:
        out = handle("web", sender, text, language=request.POST.get("language"),
                     meta=meta if isinstance(meta, dict) else None, voice_note=note)
    except Exception:
        voice_notes.discard(note)
        raise
    return JsonResponse(out)


def _json(raw):
    try:
        return json.loads(raw or "{}")
    except ValueError:
        return {}


def voice_shortcut(request):
    """Home-screen shortcut target: the chat page, ready to speak."""
    return redirect("/chat?voice=1")
