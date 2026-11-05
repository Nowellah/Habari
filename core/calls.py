"""Call with a near-live transcript for the officer. Status: SIMULATED.

A real call needs a voice provider (Africa's Talking Voice or Twilio), the
partner's agreement and the caller's consent. Here a synthetic call script is
"played": each line appears when its time has passed, as if a 10-second audio
chunk had just been transcribed. plan_chunks and merge_transcripts are the parts
a real recording would use.
"""
from django.db import transaction
from django.utils import timezone

from ai_service import lexicon_engine, sunbird_client
from core.models import Case, CallSegment, CallSession, Message
from core.utils import new_case_code

CHUNK_SECONDS, OVERLAP_SECONDS = 10, 2

# Synthetic calls only. No real child, no real recording. The Luganda script is a DRAFT.
SCRIPTS = {
    "sextortion_en": {"title": "English: pictures and money (synthetic)", "language": "en", "lines": [
        (0, 6, "Hello, is this Habari? I need to talk to someone."),
        (6, 14, "A man on Instagram has my pictures."),
        (14, 24, "He says he will post my nude pictures unless I send 50,000 shillings."),
        (24, 32, "He gave me until Friday. His number is 0772 123 456."),
        (32, 40, "I am scared. I feel like I want to die."),
        (40, 48, "Please help me. I have not told my parents."),
    ]},
    "sextortion_lg": {"title": "Luganda draft: pictures and money (synthetic)", "language": "lg", "lines": [
        (0, 6, "Hallo, ye Habari? Njagala okwogera n'omuntu."),
        (6, 16, "Omusajja ku Instagram alina ebifaananyi byange."),
        (16, 26, "Ansaba ssente nga tasindika bifaananyi byange eri buli muntu."),
        (26, 36, "Ntidde nnyo. Njagala okufa."),
    ]},
}


def plan_chunks(duration_s, size=CHUNK_SECONDS, overlap=OVERLAP_SECONDS):
    """Start and end of each audio chunk to transcribe: 10 s windows that overlap by 2 s."""
    chunks, start = [], 0
    while start < duration_s:
        end = min(start + size, duration_s)
        chunks.append((start, end))
        if end >= duration_s:
            break
        start = end - overlap
    return chunks


def merge_transcripts(parts, max_overlap_words=8):
    """Join chunk transcripts, dropping words repeated because the audio chunks overlap."""
    merged = []
    for part in parts:
        words = part.split()
        best = 0
        for k in range(min(max_overlap_words, len(merged), len(words)), 0, -1):
            if [w.lower() for w in merged[-k:]] == [w.lower() for w in words[:k]]:
                best = k
                break
        merged.extend(words[best:])
    return " ".join(merged)


def start_call(script_name, now=None):
    script = SCRIPTS[script_name]
    now = now or timezone.now()
    with transaction.atomic():
        case = Case.objects.create(code=new_case_code(), channel="voice", severity=1, language=script["language"],
                                   flags=["call", "simulated_call"], created_at=now, clock_started_at=now)
        session = CallSession.objects.create(case=case, script=script_name, language=script["language"], started_at=now)
        for i, (start, end, text) in enumerate(script["lines"]):
            CallSegment.objects.create(session=session, seq=i, start_s=start, end_s=end, text=text)
    return session


def _translate(text, language):
    if language == "en":
        return text
    return sunbird_client.translate(text, language, "en") or ""


def reveal_due(session, now=None):
    """Show every segment whose time has come. Raises the case severity as danger words appear."""
    from core import sla

    now = now or timezone.now()
    elapsed = (now - session.started_at).total_seconds()
    revealed = []
    with transaction.atomic():
        for seg in session.segments.filter(revealed_at__isnull=True, end_s__lte=elapsed).order_by("seq"):
            flags, floor = lexicon_engine.match(seg.text)
            seg.flags, seg.text_en, seg.revealed_at = flags, _translate(seg.text, session.language), now
            seg.save(update_fields=["flags", "text_en", "revealed_at"])
            Message.objects.create(case=session.case, direction="in", text=seg.text, channel="voice")
            case = Case.objects.select_for_update().get(pk=session.case_id)
            was = case.severity
            case.severity = max(case.severity, floor)
            case.flags = sorted(set(case.flags) | set(flags))
            if "authority" in flags and not case.alleged_role:
                case.alleged_role = "authority"
            case.save(update_fields=["severity", "flags", "alleged_role"])
            if case.severity > was:
                sla.reset_clock(case, f"call: severity raised {was} -> {case.severity}", now)
                sla.once(case, "severity_raised", f"{was} -> {case.severity}: said during call", now)
            revealed.append(seg)
    return revealed
