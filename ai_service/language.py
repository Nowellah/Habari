"""Language guess from the lexicon. Sunbird language ID is used on top when a token is set."""
from ai_service import lexicon_engine, sunbird_client

ASK_BELOW = 0.6  # plan §16: ask the child when confidence is below 0.6
# A second language counts as "mixed" only if it is this strong relative to the
# first. Shared loan words (ssente, school) should not trigger the question alone.
MIXED_RATIO = 0.4


def detect_language(text: str) -> dict:
    hits = lexicon_engine.language_hits(text)
    total = sum(hits.values())
    tokens = len(lexicon_engine.normalise_text(text).split())
    if total == 0:
        result = {"language": "unknown", "confidence": 0.0}
    else:
        ranked = sorted(hits.items(), key=lambda kv: kv[1], reverse=True)
        top_lang, top = ranked[0]
        confidence = round(top / total, 2)
        if tokens < 3:  # very short messages are easy to guess wrong
            confidence = round(confidence * 0.5, 2)
        result = {"language": top_lang, "confidence": confidence}
        mixed = len(ranked) > 1 and ranked[1][1] >= MIXED_RATIO * top
        result["mixed"] = mixed

    sb = sunbird_client.language_id(text)
    if sb and sb.get("language"):
        if sb["language"] == result["language"]:
            result["confidence"] = max(result["confidence"], 0.9)
        elif result["confidence"] < ASK_BELOW:
            result = {"language": sb["language"], "confidence": 0.7}
        result["provider"] = "sunbird+lexicon"
    else:
        result["provider"] = "lexicon"

    result["ask_language"] = result["confidence"] < ASK_BELOW or result.get("mixed", False)
    result.pop("mixed", None)
    return result
