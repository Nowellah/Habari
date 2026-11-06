"""Optional zero-shot classifier for triage. Off unless AI_ZEROSHOT_MODEL is set and loads."""
import os
from functools import lru_cache


@lru_cache
def zero_shot():
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
