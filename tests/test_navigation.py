import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import pytest
from pydantic import ValidationError
from models.message import Message
from models.report import Report
from models.session import Session


def test_session_model_valid():
    sid = str(uuid.uuid4())
    session = Session(session_id=sid, messages=[])
    assert session.session_id == sid
    assert session.state == "WELCOME"
    assert session.messages == []


def test_report_model_valid():
    report = Report(harm_category="cyberbullying", description="test")
    assert report.harm_category == "cyberbullying"
    assert report.description == "test"
    assert report.severity == "medium"
    assert report.language == "en"


def test_message_model_valid():
    msg = Message(role="child", text="hello")
    assert msg.role == "child"
    assert msg.text == "hello"
    assert msg.quick_replies == []


def test_invalid_message_role_raises():
    with pytest.raises(ValidationError):
        Message(role="admin", text="hello")


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


def test_session_defaults():
    sid = str(uuid.uuid4())
    session = Session(session_id=sid)
    assert session.language == "en"
    assert session.age_bracket is None
    assert session.case_code is None
    assert session.current_report is None
