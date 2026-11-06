"""
Case model — mirrors the Django core.models.Case fields used in the UI branch.
Severity uses the same 1-4 integer scale as the Django backend:
  4 = Critical (danger / self-harm)
  3 = High     (exploitation / adult abuse)
  2 = Medium   (cyberbullying)
  1 = Low      (general discomfort)
"""
from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field
import uuid


def _now() -> datetime:
    return datetime.now(timezone.utc)


CaseStatus = Literal[
    "received", "triaged", "assigned", "referred",
    "acknowledged", "in_progress", "resolved",
    "safety_check", "closed", "closed_unfounded", "closed_child_stop"
]

# Harm pick IDs matching harm_picker.json from the Django UI branch
PICKS = {
    "1": {"label_en": "I am in danger or I want to hurt myself",       "short_en": "Danger",             "default_severity": 4, "colour": "#B3261E"},
    "2": {"label_en": "Someone is asking for pictures, money or secrets","short_en": "Asked for pics/money","default_severity": 3, "colour": "#E65100"},
    "3": {"label_en": "An adult in charge is hurting me",               "short_en": "Adult hurting me",   "default_severity": 3, "colour": "#E65100"},
    "4": {"label_en": "Someone is being mean or fake",                  "short_en": "Mean or fake",       "default_severity": 2, "colour": "#F57C00"},
    "5": {"label_en": "Something upsetting or risky online",            "short_en": "Upsetting online",   "default_severity": 1, "colour": "#2E7D32"},
}

STATUS_LABELS = {
    "received":          "Received",
    "triaged":           "Triaged",
    "assigned":          "Assigned",
    "referred":          "Referred",
    "acknowledged":      "Acknowledged",
    "in_progress":       "In Progress",
    "resolved":          "Resolved",
    "safety_check":      "Safety Check-in",
    "closed":            "Closed",
    "closed_unfounded":  "Closed: Unfounded",
    "closed_child_stop": "Closed: Child Stopped",
}

SEVERITY_META = {
    4: {"label": "Critical", "bg": "#fdecea", "fg": "#B3261E", "badge": "sev-4"},
    3: {"label": "High",     "bg": "#fff3e0", "fg": "#E65100", "badge": "sev-3"},
    2: {"label": "Medium",   "bg": "#fff8e1", "fg": "#F57C00", "badge": "sev-2"},
    1: {"label": "Low",      "bg": "#e8f5e9", "fg": "#2E7D32", "badge": "sev-1"},
}


class CaseNote(BaseModel):
    note_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    officer: str = "Officer"
    text: str
    timestamp: datetime = Field(default_factory=_now)


class Case(BaseModel):
    case_code: str                        # e.g. AB-7F3Q9X
    session_id: str
    pick: str = "5"                       # harm_picker.json pick ID "1"-"5"
    harm_category: str                    # human-readable label
    description: str
    severity: int = 1                     # 1-4, matches Django integer field
    language: str = "en"
    age_bracket: Optional[str] = None
    status: CaseStatus = "received"
    submitted_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    assigned_to: Optional[str] = None
    notes: list[CaseNote] = Field(default_factory=list)
    messages: list[dict] = Field(default_factory=list)
    is_urgent: bool = False
    flags: list[str] = Field(default_factory=list)
    summary: str = ""
    triage_source: str = "rules"          # "rules" | "ai" | "rules_ai_down"

    model_config = {"extra": "ignore"}

    @property
    def severity_meta(self) -> dict:
        return SEVERITY_META.get(self.severity, SEVERITY_META[1])

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status.replace("_", " ").title())

    @property
    def pick_label(self) -> str:
        return PICKS.get(self.pick, {}).get("short_en", "—")

    @property
    def submitted_display(self) -> str:
        return self.submitted_at.strftime("%d %b %Y %H:%M")

    @property
    def age_display(self) -> str:
        return self.age_bracket or "Not specified"

    @property
    def is_open(self) -> bool:
        return self.status not in ("resolved", "closed", "closed_unfounded", "closed_child_stop")
