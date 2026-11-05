"""Tests for model validation and session management."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import pytest
from datetime import timezone
from pydantic import ValidationError

from models.message import Message
from models.report import Report
from models.session import Session
from services.session import SessionManager


# ── Message model ──────────────────────────────────────────────────────────────

def test_message_model_valid():
    msg = Message(role="child", text="hello")
    assert msg.role == "child"
    assert msg.text == "hello"
    assert msg.quick_replies == []


def test_message_timestamp_is_timezone_aware():
    """Timestamps must be timezone-aware (UTC) — no deprecated utcnow."""
    msg = Message(role="bot", text="hi")
    assert msg.timestamp.tzinfo is not None
    assert msg.timestamp.utcoffset().total_seconds() == 0


def test_invalid_message_role_raises():
    with pytest.raises(ValidationError):
        Message(role="admin", text="hello")


# ── Report model ───────────────────────────────────────────────────────────────

def test_report_model_valid():
    report = Report(harm_category="cyberbullying", description="test desc")
    assert report.harm_category == "cyberbullying"
    assert report.description == "test desc"
    assert report.severity == "medium"
    assert report.language == "en"
    assert report.attachments == []


def test_report_with_age_bracket():
    report = Report(harm_category="threat", description="x", age_bracket="13–15")
    assert report.age_bracket == "13–15"


def test_report_severity_default():
    report = Report(harm_category="x", description="y")
    assert report.severity == "medium"


# ── Session model ──────────────────────────────────────────────────────────────

def test_session_model_valid():
    sid = str(uuid.uuid4())
    session = Session(session_id=sid, messages=[])
    assert session.session_id == sid
    assert session.state == "WELCOME"
    assert session.messages == []


def test_session_defaults():
    sid = str(uuid.uuid4())
    session = Session(session_id=sid)
    assert session.language == "en"
    assert session.age_bracket is None
    assert session.case_code is None
    assert session.current_report is None
    assert session.harm_category is None


def test_session_with_messages():
    sid = str(uuid.uuid4())
    msgs = [
        Message(role="child", text="hi"),
        Message(role="bot", text="hello", quick_replies=["opt1", "opt2"]),
    ]
    session = Session(session_id=sid, messages=msgs)
    assert len(session.messages) == 2
    assert session.messages[0].role == "child"
    assert session.messages[1].quick_replies == ["opt1", "opt2"]


def test_session_harm_category_field():
    sid = str(uuid.uuid4())
    session = Session(session_id=sid, harm_category="cyberbullying")
    assert session.harm_category == "cyberbullying"


def test_session_ignores_extra_fields():
    """model_config extra=ignore must not raise on unknown kwargs."""
    sid = str(uuid.uuid4())
    # Pydantic v2: model_validate with extra field
    session = Session.model_validate({"session_id": sid, "_unknown_field": "x"})
    assert session.session_id == sid


# ── SessionManager ─────────────────────────────────────────────────────────────

def test_session_manager_create_and_get():
    sm = SessionManager()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    session = sm.get_session(sid)
    assert session is not None
    assert session.session_id == sid


def test_session_manager_update():
    sm = SessionManager()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    sm.update_session(sid, language="lg", age_bracket="13–15")
    session = sm.get_session(sid)
    assert session.language == "lg"
    assert session.age_bracket == "13–15"


def test_session_manager_missing_session_returns_none():
    sm = SessionManager()
    result = sm.get_session("does-not-exist")
    assert result is None


def test_session_manager_update_missing_returns_none():
    sm = SessionManager()
    result = sm.update_session("no-such-id", state="CHAT_READY")
    assert result is None


def test_session_manager_clear():
    sm = SessionManager()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    sm.clear_session(sid)
    assert sm.get_session(sid) is None


def test_session_manager_isolation():
    """Two sessions must not share state."""
    sm = SessionManager()
    sid1, sid2 = str(uuid.uuid4()), str(uuid.uuid4())
    sm.create_session(sid1)
    sm.create_session(sid2)
    sm.update_session(sid1, language="sw")
    s1 = sm.get_session(sid1)
    s2 = sm.get_session(sid2)
    assert s1.language == "sw"
    assert s2.language == "en"
