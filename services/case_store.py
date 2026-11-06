"""
CaseStore — thread-safe in-memory store for submitted cases.

Mirrors the Django core.models.Case structure from the UI branch.
In production, swap this singleton for calls to the Django REST API.
The interface is intentionally kept thin so the swap is a one-file change.
"""
from __future__ import annotations
import threading
import random
import string
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from models.case import Case, CaseNote, CaseStatus, PICKS


# ── helpers ───────────────────────────────────────────────────────────────────

def _demo_code() -> str:
    chars = string.ascii_uppercase + string.digits
    prefix = "".join(random.choices(string.ascii_uppercase, k=2))
    suffix = "".join(random.choices(chars, k=6))
    return f"{prefix}-{suffix}"


def _pick_for_category(harm_category: str) -> str:
    """Map a harm category string to a harm_picker.json pick ID."""
    h = harm_category.lower()
    if any(w in h for w in ("danger", "hurt myself", "suicid", "self-harm", "unsafe")):
        return "1"
    if any(w in h for w in ("picture", "money", "secret", "nude", "exploit")):
        return "2"
    if any(w in h for w in ("adult", "teacher", "guardian", "parent", "hurting me")):
        return "3"
    if any(w in h for w in ("mean", "bully", "fake", "pretend", "impersonat")):
        return "4"
    return "5"


def _severity_for_pick(pick: str) -> int:
    return PICKS.get(pick, {}).get("default_severity", 1)


# ── CaseStore ──────────────────────────────────────────────────────────────────

class CaseStore:
    """Thread-safe in-memory case registry."""

    def __init__(self) -> None:
        self._cases: dict[str, Case] = {}
        self._lock = threading.Lock()
        self._seed_demo_cases()

    # ── Public API ─────────────────────────────────────────────────────────

    def register_case(
        self,
        session_id: str,
        harm_category: str,
        description: str,
        severity: Optional[int] = None,
        language: str = "en",
        age_bracket: Optional[str] = None,
        messages: Optional[list[dict]] = None,
        is_urgent: bool = False,
        case_code: Optional[str] = None,
    ) -> Case:
        """Create and store a new case from a child's submission."""
        code = (case_code or _demo_code()).upper()
        pick = _pick_for_category(harm_category)
        sev = severity if severity is not None else _severity_for_pick(pick)
        # Urgency always floors to severity 3
        if is_urgent and sev < 3:
            sev = 3

        case = Case(
            case_code=code,
            session_id=session_id,
            pick=pick,
            harm_category=harm_category,
            description=description,
            severity=sev,
            language=language,
            age_bracket=age_bracket,
            messages=messages or [],
            is_urgent=is_urgent,
            flags=["urgent"] if is_urgent else [],
        )
        with self._lock:
            self._cases[code] = case
        return case

    def get_case(self, case_code: str) -> Optional[Case]:
        with self._lock:
            return self._cases.get(case_code.upper().strip())

    def all_cases(self) -> list[Case]:
        with self._lock:
            return sorted(
                self._cases.values(),
                key=lambda c: (-(c.severity), c.submitted_at),
            )

    def update_status(self, case_code: str, status: CaseStatus) -> Optional[Case]:
        with self._lock:
            case = self._cases.get(case_code.upper())
            if case is None:
                return None
            updated = case.model_copy(update={
                "status": status,
                "updated_at": datetime.now(timezone.utc),
            })
            self._cases[case_code.upper()] = updated
            return updated

    def assign_case(self, case_code: str, officer_name: str) -> Optional[Case]:
        with self._lock:
            case = self._cases.get(case_code.upper())
            if case is None:
                return None
            updated = case.model_copy(update={
                "assigned_to": officer_name,
                "status": "assigned",
                "updated_at": datetime.now(timezone.utc),
            })
            self._cases[case_code.upper()] = updated
            return updated

    def add_note(self, case_code: str, text: str, officer: str = "Officer") -> Optional[Case]:
        with self._lock:
            case = self._cases.get(case_code.upper())
            if case is None:
                return None
            note = CaseNote(officer=officer, text=text)
            updated = case.model_copy(update={
                "notes": list(case.notes) + [note],
                "updated_at": datetime.now(timezone.utc),
            })
            self._cases[case_code.upper()] = updated
            return updated

    def acknowledge(self, case_code: str) -> Optional[Case]:
        with self._lock:
            case = self._cases.get(case_code.upper())
            if case is None:
                return None
            if case.status == "received":
                updated = case.model_copy(update={
                    "status": "triaged",
                    "updated_at": datetime.now(timezone.utc),
                })
                self._cases[case_code.upper()] = updated
                return updated
            return case

    # ── Metrics ────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        cases = self.all_cases()
        total = len(cases)
        by_severity = {4: 0, 3: 0, 2: 0, 1: 0}
        by_status:   dict[str, int] = {}
        by_pick:     dict[str, int] = {}
        urgent = 0
        open_count = 0

        for c in cases:
            by_severity[c.severity] = by_severity.get(c.severity, 0) + 1
            by_status[c.status]     = by_status.get(c.status, 0) + 1
            by_pick[c.pick_label]   = by_pick.get(c.pick_label, 0) + 1
            if c.is_urgent:
                urgent += 1
            if c.is_open:
                open_count += 1

        return {
            "total":       total,
            "open":        open_count,
            "urgent":      urgent,
            "by_severity": by_severity,  # {4: n, 3: n, 2: n, 1: n}
            "by_status":   by_status,
            "by_pick":     by_pick,      # {"Danger": n, ...}
        }

    # ── Demo seeding ───────────────────────────────────────────────────────

    def _seed_demo_cases(self) -> None:
        now = datetime.now(timezone.utc)
        seed = [
            {
                "pick": "2", "severity": 4,
                "harm_category": "Someone is asking me for pictures, money, or secrets.",
                "description": "A man on Instagram keeps asking me to send him photos. He says he loves me.",
                "age_bracket": "13–15", "status": "received", "is_urgent": True,
                "language": "en", "delta_hours": 1,
                "flags": ["urgent", "sextortion_risk"],
            },
            {
                "pick": "1", "severity": 4,
                "harm_category": "I am in danger or thinking about hurting myself.",
                "description": "I have been feeling like I don't want to be here anymore. Everything is too much.",
                "age_bracket": "16–17", "status": "assigned", "is_urgent": True,
                "language": "en", "delta_hours": 3,
                "assigned_to": "Officer Nakato",
                "flags": ["urgent", "self_harm"],
            },
            {
                "pick": "3", "severity": 3,
                "harm_category": "An adult in charge is hurting me.",
                "description": "My teacher hits me when I get answers wrong. It happens at least twice a week.",
                "age_bracket": "10–12", "status": "triaged", "is_urgent": False,
                "language": "en", "delta_hours": 6,
                "flags": ["authority_figure"],
            },
            {
                "pick": "4", "severity": 3,
                "harm_category": "Someone is being mean to me or pretending to be someone else.",
                "description": "Some kids from school made a fake account with my name and are posting bad things.",
                "age_bracket": "13–15", "status": "in_progress", "is_urgent": False,
                "language": "en", "delta_hours": 12,
                "assigned_to": "Officer Ssemakula",
                "flags": ["impersonation"],
            },
            {
                "pick": "5", "severity": 1,
                "harm_category": "Something online is making me uncomfortable.",
                "description": "A game I play keeps showing me strange videos that I don't like.",
                "age_bracket": "Under 10", "status": "received", "is_urgent": False,
                "language": "en", "delta_hours": 24,
            },
            {
                "pick": "2", "severity": 3,
                "harm_category": "Someone is asking me for pictures, money, or secrets.",
                "description": "Someone on TikTok told me to keep our chat secret from my parents.",
                "age_bracket": "10–12", "status": "resolved", "is_urgent": False,
                "language": "en", "delta_hours": 48,
                "assigned_to": "Officer Nakato",
            },
            {
                "pick": "5", "severity": 2,
                "harm_category": "Something online is making me uncomfortable.",
                "description": "I keep getting messages from strangers asking where I live.",
                "age_bracket": "16–17", "status": "triaged", "is_urgent": False,
                "language": "lg", "delta_hours": 36,
            },
            {
                "pick": "3", "severity": 4,
                "harm_category": "An adult in charge is hurting me.",
                "description": "My uncle threatens me and says nobody will believe me.",
                "age_bracket": "13–15", "status": "referred", "is_urgent": True,
                "language": "en", "delta_hours": 72,
                "assigned_to": "Officer Ssemakula",
                "flags": ["urgent", "authority_figure"],
            },
        ]

        for d in seed:
            code = _demo_code()
            submitted = now - timedelta(hours=d["delta_hours"])
            case = Case(
                case_code=code,
                session_id=str(uuid.uuid4()),
                pick=d["pick"],
                harm_category=d["harm_category"],
                description=d["description"],
                severity=d["severity"],
                age_bracket=d.get("age_bracket"),
                status=d["status"],
                is_urgent=d.get("is_urgent", False),
                language=d.get("language", "en"),
                submitted_at=submitted,
                updated_at=submitted,
                assigned_to=d.get("assigned_to"),
                flags=d.get("flags", []),
            )
            self._cases[code] = case


# Module-level singleton — shared across the entire NiceGUI process
case_store = CaseStore()
