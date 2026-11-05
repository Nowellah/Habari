"""Composition of the reply a child sees from reviewed templates."""
from .config import Settings
from .content import select_bundle
from .routing import build_routing
from .schemas import ChatResponse, Guidance, MessageRequest, PathOption, SafeAction, Severity, TriageResult

SHORT_MESSAGE_LIMIT = 160
_SHORT_CHANNELS = frozenset({"sms", "ussd"})


def _join(*parts: str | None) -> str:
    return " ".join(part for part in parts if part)


def helpline_line(bundle: dict, helpline: str | None, short: bool) -> str:
    """The sentence that points a child to a real person, with or without a configured number."""
    if helpline:
        return bundle["helpline_line_short" if short else "helpline_line"].replace("{helpline}", helpline)
    return bundle["no_helpline_line_short" if short else "no_helpline_line"]


def _short_reply(bundle: dict, body: str, note: str | None, helpline_part: str) -> str:
    """Fit a reply into one SMS or USSD screen by dropping the least important parts first."""
    prefix = bundle["disclosure_short"]
    candidates = (
        _join(prefix, body, note, helpline_part),
        _join(prefix, body, helpline_part),
        _join(body, helpline_part),
        body,
    )
    for candidate in candidates:
        if len(candidate) <= SHORT_MESSAGE_LIMIT:
            return candidate
    return body[:SHORT_MESSAGE_LIMIT]


def _long_reply(bundle: dict, body: str, note: str | None, helpline_part: str, danger: bool) -> str:
    disclosure = bundle["disclosure"]
    if danger:
        return _join(body, helpline_part, disclosure)
    return _join(disclosure, body, note, helpline_part)


def build_chat_response(
    request: MessageRequest,
    result: TriageResult,
    settings: Settings,
    guidance: Guidance | None = None,
) -> ChatResponse:
    bundle, language_used, fell_back = select_bundle(request.language)
    helpline = settings.helpline_number
    category = bundle["categories"][result.category.value]
    short_channel = request.channel in _SHORT_CHANNELS

    helpline_part = helpline_line(bundle, helpline, short_channel)

    note = None
    if result.external_only and not result.danger:
        note = bundle["external_only_note_short" if short_channel else "external_only_note"]

    if short_channel:
        reply = _short_reply(bundle, category["short"], note, helpline_part)
        clarifying_question = bundle["clarify_short"] if result.needs_clarification else None
    else:
        reply = _long_reply(bundle, category["reply"], note, helpline_part, result.danger)
        clarifying_question = bundle["clarify"] if result.needs_clarification else None

    path_options = [PathOption(**option) for option in bundle["path_options"]]
    if result.severity == Severity.S4:
        path_options = path_options[:1]

    return ChatResponse(
        **result.model_dump(),
        reply=reply,
        clarifying_question=clarifying_question,
        safe_actions=[SafeAction(**action) for action in bundle["safe_actions"]],
        path_options=path_options,
        routing=build_routing(result),
        language_used=language_used,
        language_fallback=fell_back,
        needs_native_review=fell_back,
        content_review_status=bundle["meta"]["review_status"],
        helpline=helpline,
        helpline_configured=helpline is not None,
        guidance=guidance,
    )
