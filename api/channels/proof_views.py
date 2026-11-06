"""Proof upload from the web chat: a screenshot or PDF goes onto the child's open case."""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from channels import proofs
from channels.gateway import add_proof


@csrf_exempt  # the anonymous chat page sets no cookies, so it has no CSRF token
@require_POST
def proof_upload(request):
    sender = (request.POST.get("sender_id") or "").strip()
    upload = request.FILES.get("file")
    if not sender or upload is None or upload.size == 0:
        return JsonResponse({"message": "No file was received."}, status=400)
    if upload.size > proofs.MAX_BYTES:
        return JsonResponse({"message": "That file is too big. Please send one under 8 MB."}, status=413)
    data = upload.read()
    kind = proofs.sniff(data)
    if kind is None:
        return JsonResponse({"message": "I could not use that file. Please send a screenshot or a PDF."}, status=415)
    note = proofs.save(data, *kind)
    try:
        out, kept = add_proof(sender, note, data)
    except Exception:
        proofs.discard(note)
        raise
    if not kept:
        proofs.discard(note)
    return JsonResponse(out)
