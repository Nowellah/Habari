from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Message(BaseModel):
    role: Literal["child", "bot"]
    text: str
    timestamp: datetime = Field(default_factory=_now_utc)
    quick_replies: list[str] = []
