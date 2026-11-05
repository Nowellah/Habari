"""Request and response models shared by the API and the triage engine."""
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_MESSAGE_LENGTH = 2000
MAX_QUERY_LENGTH = 500


class Severity(str, Enum):
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"

    @property
    def rank(self) -> int:
        return int(self.value[1])

    @classmethod
    def from_rank(cls, rank: int) -> "Severity":
        return cls(f"S{min(max(rank, 1), 4)}")


class Category(str, Enum):
    SELF_HARM = "self_harm"
    IMMEDIATE_DANGER = "immediate_danger"
    ABUSE = "abuse"
    SEXTORTION = "sextortion"
    GROOMING = "grooming"
    HARASSMENT = "harassment"
    ACCOUNT_SCAM = "account_scam"
    EXPOSURE = "exposure"
    OTHER = "other"


Language = Literal["en", "lg"]
Channel = Literal["chat", "sms", "ussd"]
AllegedRole = Literal["stranger", "online_contact", "peer", "family", "teacher", "guardian", "unknown"]
CategoryHint = Literal[
    "self_harm",
    "immediate_danger",
    "abuse",
    "sextortion",
    "grooming",
    "harassment",
    "account_scam",
    "exposure",
    "other",
]


def _strip_not_blank(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("text must not be blank")
    return stripped


class MessageRequest(BaseModel):
    """A single message from a child plus optional context chosen by the child."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    language: Language = "en"
    channel: Channel = "chat"
    alleged_role: AllegedRole | None = None
    happening_now: bool | None = None
    category_hint: CategoryHint | None = None

    @field_validator("message")
    @classmethod
    def message_must_have_content(cls, value: str) -> str:
        return _strip_not_blank(value)


class KnowledgeRequest(BaseModel):
    """A question to look up in the reviewed knowledge base."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    language: Language = "en"

    @field_validator("query")
    @classmethod
    def query_must_have_content(cls, value: str) -> str:
        return _strip_not_blank(value)


class TriageResult(BaseModel):
    """Classification of a message. Contains rule identifiers, never message text."""

    severity: Severity
    category: Category
    confidence: Literal["high", "low"]
    matched_rules: list[str]
    danger: bool
    human_review: bool
    external_only: bool
    needs_clarification: bool


class SafeAction(BaseModel):
    id: str
    text: str


class PathOption(BaseModel):
    id: str
    label: str


class Routing(BaseModel):
    external_only: bool
    allowed_routes: list[str]
    human_decision_required: bool


class Guidance(BaseModel):
    """An approved knowledge base entry. Text is never generated."""

    id: str
    title: str
    answer: str
    review_status: str
    score: float


class KnowledgeResponse(BaseModel):
    matched: bool
    guidance: Guidance | None
    backend: str
    best_score: float


class ChatResponse(TriageResult):
    reply: str
    clarifying_question: str | None
    safe_actions: list[SafeAction]
    path_options: list[PathOption]
    routing: Routing
    language_used: Language
    language_fallback: bool
    needs_native_review: bool
    content_review_status: str
    helpline: str | None
    helpline_configured: bool
    guidance: Guidance | None = None


Step = Literal["describe", "ask_feeling", "ask_now", "ask_who", "offer", "ask_question", "report_review", "edit", "danger_check", "done"]
SelfRating = Literal["feel_little", "feel_lot", "feel_scared", "feel_danger", "feel_skip"]
MAX_NARRATIVE_ENTRIES = 5
MAX_STATE_RULES = 40


class ConversationState(BaseModel):
    """What the browser carries between turns. It holds the child's words only for their own report review."""

    model_config = ConfigDict(extra="forbid")

    step: Step = "describe"
    severity: Severity = Severity.S1
    category: Category = Category.OTHER
    confidence: Literal["high", "low"] = "high"
    rules: list[str] = Field(default_factory=list, max_length=MAX_STATE_RULES)
    external_only: bool = False
    human_review: bool = False
    danger: bool = False
    alleged_role: AllegedRole | None = None
    happening_now: bool | None = None
    self_rating: SelfRating | None = None
    asked_feeling: bool = False
    asked_now: bool = False
    asked_who: bool = False
    external_noted: bool = False
    clarify_count: int = Field(default=0, ge=0, le=5)
    narrative: list[str] = Field(default_factory=list, max_length=MAX_NARRATIVE_ENTRIES)

    @field_validator("narrative")
    @classmethod
    def narrative_entries_are_bounded(cls, value: list[str]) -> list[str]:
        if any(len(entry) > MAX_MESSAGE_LENGTH for entry in value):
            raise ValueError("narrative entry too long")
        return value

    @field_validator("rules")
    @classmethod
    def rule_ids_are_short(cls, value: list[str]) -> list[str]:
        if any(len(rule) > 60 for rule in value):
            raise ValueError("rule id too long")
        return value


class TurnRequest(BaseModel):
    """One step of the guided conversation: free text or a chosen option, never both."""

    model_config = ConfigDict(extra="forbid")

    state: ConversationState | None = None
    text: str | None = Field(default=None, min_length=1, max_length=MAX_MESSAGE_LENGTH)
    choice: str | None = Field(default=None, min_length=1, max_length=40)
    language: Language = "en"
    channel: Channel = "chat"
    category_hint: CategoryHint | None = None

    @model_validator(mode="after")
    def exactly_one_input(self) -> "TurnRequest":
        if self.text is not None:
            self.text = _strip_not_blank(self.text)
            if self.choice is not None:
                raise ValueError("send text or a choice, not both")
        return self


class BotMessage(BaseModel):
    kind: Literal["text", "danger", "guidance", "list"]
    text: str = ""
    title: str | None = None
    items: list[str] | None = None


class Choice(BaseModel):
    id: str
    label: str


class CaseDraft(BaseModel):
    """What the case system receives once a child has confirmed. Nothing is stored by this service."""

    severity: Severity
    category: Category
    channel: Channel
    language: Language
    external_only: bool
    human_review: bool
    summary: str
    allowed_routes: list[str]
    consent_confirmed: bool


class TurnResponse(BaseModel):
    state: ConversationState
    messages: list[BotMessage]
    choices: list[Choice]
    menu_text: str | None
    accepts_text: bool
    ended: bool
    assessment: TriageResult
    routing: Routing
    case_draft: CaseDraft | None
    language_used: Language
    needs_native_review: bool
    content_review_status: str
    helpline: str | None
    helpline_configured: bool
