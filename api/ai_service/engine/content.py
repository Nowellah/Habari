"""Loading of reviewed reply content.

Reply text lives in JSON files so that child protection staff and native
speakers can review it without reading code. A language bundle is used only
when it is complete and marked approved; otherwise English is used and the
response says so.
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

from .schemas import Category

logger = logging.getLogger("habari.ai")

CONTENT_DIR = Path(__file__).parent / "content"
APPROVED = "approved"

_REQUIRED_KEYS = (
    "meta",
    "disclosure",
    "disclosure_short",
    "helpline_line",
    "helpline_line_short",
    "no_helpline_line",
    "no_helpline_line_short",
    "external_only_note",
    "external_only_note_short",
    "clarify",
    "clarify_short",
    "safe_actions",
    "path_options",
    "categories",
    "flow",
)

REQUIRED_PROMPTS = (
    "welcome", "ask_now", "ask_who", "offer", "ask_question", "no_answer", "safe_actions_title",
    "report_intro", "report_what", "report_words", "report_who_external", "report_who_default",
    "report_who_serious", "report_title", "report_confirm", "report_ready", "edit_prompt",
    "external_notice", "ask_feeling", "feeling_higher", "danger_check", "danger_safe", "danger_unsafe", "please_choose", "closing",
)
REQUIRED_CHOICES = (
    "yes", "no", "not_sure", "stranger", "online_contact", "peer", "family", "teacher", "guardian",
    "unknown", "talk_to_person", "report_privately", "keep_proof", "just_information", "done",
    "confirm_send", "edit", "not_now", "safe_yes", "safe_no",
    "feel_little", "feel_lot", "feel_scared", "feel_danger", "feel_skip",
)


@lru_cache(maxsize=None)
def _load(language: str) -> dict:
    path = CONTENT_DIR / f"{language}.json"
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("content file for %s could not be read: %s", language, type(exc).__name__)
        return {}


def is_complete(bundle: dict) -> bool:
    """True when every required key and every category entry is present."""
    if not all(key in bundle for key in _REQUIRED_KEYS):
        return False
    categories = bundle["categories"]
    if not all(
        category.value in categories
        and "reply" in categories[category.value]
        and "short" in categories[category.value]
        for category in Category
    ):
        return False
    return _flow_is_complete(bundle["flow"])


def _flow_is_complete(flow: dict) -> bool:
    prompts = flow.get("prompts", {})
    choices = flow.get("choices", {})
    labels = flow.get("category_labels", {})
    return (
        all(key in prompts and {"long", "short"} <= prompts[key].keys() for key in REQUIRED_PROMPTS)
        and all(key in choices and "short" in choices[key] for key in REQUIRED_CHOICES)
        and all(c.value in labels and {"label", "short"} <= labels[c.value].keys() for c in Category)
    )


def select_bundle(language: str) -> tuple[dict, str, bool]:
    """Return (bundle, language_used, fell_back_to_english)."""
    english = _load("en")
    if not is_complete(english):
        raise RuntimeError("English content bundle is missing or incomplete")
    if language == "en":
        return english, "en", False
    candidate = _load(language)
    if is_complete(candidate) and candidate["meta"].get("review_status") == APPROVED:
        return candidate, language, False
    return english, "en", True
