"""Settings for the knowledge answers, read from environment variables."""
import logging
import os
import re
from dataclasses import dataclass

logger = logging.getLogger("habari.ai")

DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_EMBED_THRESHOLD = 0.6
DEFAULT_LEXICAL_THRESHOLD = 0.3
DEFAULT_OLLAMA_TIMEOUT = 3.0


@dataclass(frozen=True)
class Settings:
    """Values that must come from configuration and never from code."""

    ollama_url: str | None = None
    embed_model: str = DEFAULT_EMBED_MODEL
    embed_threshold: float = DEFAULT_EMBED_THRESHOLD
    lexical_threshold: float = DEFAULT_LEXICAL_THRESHOLD
    ollama_timeout: float = DEFAULT_OLLAMA_TIMEOUT


def _read_float(name: str, default: float, low: float, high: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        value = None
    if value is None or not low <= value <= high:
        logger.warning("%s is not a number between %s and %s and was ignored", name, low, high)
        return default
    return value


def _read_ollama_url() -> str | None:
    raw = os.getenv("HABARI_OLLAMA_URL", "").strip()
    if not raw:
        return None
    if not re.match(r"^https?://[^\s/]+(:\d+)?/?$", raw):
        logger.warning("HABARI_OLLAMA_URL is not a plain http or https address and was ignored")
        return None
    return raw.rstrip("/")


def get_settings() -> Settings:
    """Read settings on every call so a changed environment takes effect."""
    return Settings(
        ollama_url=_read_ollama_url(),
        embed_model=os.getenv("HABARI_EMBED_MODEL", "").strip() or DEFAULT_EMBED_MODEL,
        embed_threshold=_read_float("HABARI_EMBED_THRESHOLD", DEFAULT_EMBED_THRESHOLD, 0.0, 1.0),
        lexical_threshold=_read_float("HABARI_LEXICAL_THRESHOLD", DEFAULT_LEXICAL_THRESHOLD, 0.0, 1.0),
        ollama_timeout=_read_float("HABARI_OLLAMA_TIMEOUT", DEFAULT_OLLAMA_TIMEOUT, 0.5, 60.0),
    )
