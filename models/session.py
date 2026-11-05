from typing import Optional
from pydantic import BaseModel, Field
from .message import Message
from .report import Report


class Session(BaseModel):
    session_id: str
    state: str = "WELCOME"
    age_bracket: Optional[str] = None
    language: str = "en"
    messages: list[Message] = Field(default_factory=list)
    current_report: Optional[Report] = None
    case_code: Optional[str] = None
    harm_category: Optional[str] = None   # selected reporting category

    model_config = {"extra": "ignore"}  # silently drop unknown kwargs
