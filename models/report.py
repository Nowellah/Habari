from typing import Optional
from pydantic import BaseModel


class Report(BaseModel):
    harm_category: str
    description: str
    language: str = "en"
    age_bracket: Optional[str] = None
    severity: str = "medium"
    attachments: list = []
