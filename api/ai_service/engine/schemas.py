"""Result types of the rule engine."""
from enum import Enum
from typing import Literal

from pydantic import BaseModel


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
