from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["child", "bot"]
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    quick_replies: list[str] = []
