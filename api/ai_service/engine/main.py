"""HTTP interface of the Habari chat and triage service."""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .chat import build_chat_response
from .config import Settings, get_settings
from .conversation import take_turn
from .retrieval import SearchResult, search
from .schemas import (
    ChatResponse,
    Guidance,
    KnowledgeRequest,
    KnowledgeResponse,
    MessageRequest,
    Severity,
    TriageResult,
    TurnRequest,
    TurnResponse,
)
from .triage import safe_triage

logger = logging.getLogger("habari.ai")

STATIC_DIR = Path(__file__).parent / "static"
_PAGE_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
}

app = FastAPI(title="Habari chat and triage service", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def page_security_headers(request: Request, call_next):
    """Lock down the child-facing page without affecting the interactive API docs."""
    response = await call_next(request)
    if request.url.path in ("/", "/favicon.ico") or request.url.path.startswith("/static"):
        response.headers.update(_PAGE_HEADERS)
    return response


def _assess(request: MessageRequest) -> TriageResult:
    result = safe_triage(
        request.message,
        language=request.language,
        happening_now=request.happening_now,
        alleged_role=request.alleged_role,
        category_hint=request.category_hint,
    )
    logger.info(
        "assessed severity=%s category=%s channel=%s rules=%s",
        result.severity.value,
        result.category.value,
        request.channel,
        ",".join(result.matched_rules),
    )
    return result


def _to_guidance(outcome: SearchResult) -> Guidance | None:
    if outcome.match is None:
        return None
    entry = outcome.match.entry
    return Guidance(
        id=entry.id,
        title=entry.title,
        answer=entry.answer,
        review_status=outcome.match.review_status,
        score=outcome.match.score,
    )


def _guidance_for(request: MessageRequest, result: TriageResult, settings: Settings) -> Guidance | None:
    """Attach knowledge only to calm English chat replies, never to danger or high-severity cases."""
    if request.channel != "chat" or request.language != "en" or result.severity.rank > Severity.S2.rank:
        return None
    try:
        outcome = search(request.message, request.language, settings)
    except Exception as exc:  # noqa: BLE001 - guidance is optional and must never break the reply
        logger.error("guidance lookup failed with %s", type(exc).__name__)
        return None
    return _to_guidance(outcome)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Report which fields failed without echoing what the child wrote."""
    problems = [
        {"field": ".".join(str(part) for part in error["loc"] if part != "body"), "problem": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": problems})


@app.exception_handler(Exception)
async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled error %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "internal_error"})


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "icon.svg", media_type="image/svg+xml")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/ai/triage", response_model=TriageResult)
def triage_endpoint(request: MessageRequest) -> TriageResult:
    return _assess(request)


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: MessageRequest) -> ChatResponse:
    settings = get_settings()
    result = _assess(request)
    return build_chat_response(request, result, settings, _guidance_for(request, result, settings))


@app.post("/api/knowledge/search", response_model=KnowledgeResponse)
def knowledge_search_endpoint(request: KnowledgeRequest) -> KnowledgeResponse:
    outcome = search(request.query, request.language, get_settings())
    logger.info(
        "knowledge search backend=%s matched=%s entry=%s",
        outcome.backend,
        outcome.match is not None,
        outcome.match.entry.id if outcome.match else "-",
    )
    return KnowledgeResponse(
        matched=outcome.match is not None,
        guidance=_to_guidance(outcome),
        backend=outcome.backend,
        best_score=outcome.best_score,
    )


@app.post("/api/conversation/turn", response_model=TurnResponse)
def conversation_turn_endpoint(request: TurnRequest) -> TurnResponse:
    response = take_turn(request, get_settings())
    logger.info(
        "turn step=%s severity=%s category=%s channel=%s",
        response.state.step,
        response.state.severity.value,
        response.state.category.value,
        request.channel,
    )
    return response
