"""Habari AI service. Run from the project root:

    uvicorn ai_service.app:app --port 8001

Works with no tokens and no GPU (lexicon rules). Set SUNBIRD_TOKEN for Sunbird
language ID and translation, and AI_ZEROSHOT_MODEL to load a zero-shot model.
"""
import os
from functools import lru_cache

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ai_service import lexicon_engine, speech, sunbird_client
from ai_service.language import detect_language
from ai_service.synthesis import summarise
from ai_service.triage import triage

app = FastAPI(title="Habari AI service", version="0.2")

MAX_TEXT = 5000
MAX_AUDIO = 10 * 1024 * 1024  # about 10 minutes of a voice note
TYPE_INSTEAD = "Please type your message instead."


class TextIn(BaseModel):
    text: str = Field("", max_length=MAX_TEXT)


class TriageIn(TextIn):
    pick: str | None = None
    language: str | None = None


class MessageIn(BaseModel):
    text: str = Field("", max_length=MAX_TEXT)
    at: str = ""


class SummariseIn(BaseModel):
    messages: list[MessageIn] = Field(default_factory=list, max_length=50)


class TranslateIn(TextIn):
    source: str
    target: str = "en"


@lru_cache
def zero_shot():
    """Optional zero-shot classifier. Returns None unless AI_ZEROSHOT_MODEL is set and loads."""
    model = os.getenv("AI_ZEROSHOT_MODEL", "").strip()
    if not model:
        return None
    try:
        from transformers import pipeline  # heavy, only imported when asked for
        pipe = pipeline("zero-shot-classification", model=model)
    except Exception:
        return None

    def classify(text, labels):
        out = pipe(text, candidate_labels=[label.replace("_", " ") for label in labels])
        return {label.replace(" ", "_"): score for label, score in zip(out["labels"], out["scores"])}

    return classify


@app.get("/health")
def health():
    return {
        "status": "ok",
        "lexicon_version": lexicon_engine.load().get("version"),
        "sunbird": sunbird_client.enabled(),
        "zero_shot_model": os.getenv("AI_ZEROSHOT_MODEL") or None,
        "zero_shot_loaded": zero_shot() is not None,
        "speech_to_text": speech.engines_available(),
    }


@app.post("/language")
def language(body: TextIn):
    return detect_language(body.text)


@app.post("/triage")
def triage_endpoint(body: TriageIn):
    return triage(body.text, pick=body.pick, language=body.language, classifier=zero_shot())


@app.post("/translate")
def translate(body: TranslateIn):
    if body.source == body.target:
        return {"text": body.text, "translated": False, "provider": None}
    out = sunbird_client.translate(body.text, body.source, body.target)
    if out is None:
        # No provider available: hand back the original so a human can read it.
        return {"text": body.text, "translated": False, "provider": None}
    return {"text": out, "translated": True, "provider": "sunbird"}


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form("")):
    data = await audio.read(MAX_AUDIO + 1)
    if not data:
        raise HTTPException(400, "The voice note is empty.")
    if len(data) > MAX_AUDIO:
        raise HTTPException(413, "The voice note is too long.")
    engine = speech.get_transcriber()
    if engine is None:
        raise HTTPException(503, "No speech-to-text engine is set up. " + TYPE_INSTEAD)
    try:
        out = engine(data, language or None)
    except Exception:
        out = None
    text = ((out or {}).get("text") or "").strip()
    if not text:
        raise HTTPException(503, "We could not turn the voice note into words. " + TYPE_INSTEAD)
    return {"text": text, "language": out.get("language") or language or "unknown", "engine": out.get("engine")}


@app.post("/summarise")
def summarise_endpoint(body: SummariseIn):
    return summarise([m.model_dump() for m in body.messages])
