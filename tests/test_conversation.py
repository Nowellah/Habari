import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import pytest
from services.conversation import ConversationService
from services.session import SessionManager


def make_service():
    """Return a ConversationService with a fresh SessionManager."""
    sm = SessionManager()
    svc = ConversationService()
    # Override the session_manager used inside conversation_service for isolation
    import services.conversation as conv_mod
    conv_mod.session_manager = sm
    return svc, sm


def test_init_returns_greeting_and_five_quick_replies():
    svc, sm = make_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    reply, qr = svc.process_message(sid, "__init__")
    assert isinstance(reply, str)
    assert len(reply) > 0
    assert isinstance(qr, list)
    assert len(qr) == 5


def test_harm_category_returns_reply():
    svc, sm = make_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    # Init first
    svc.process_message(sid, "__init__")
    reply, _ = svc.process_message(sid, "I am in danger or thinking about hurting myself.")
    assert isinstance(reply, str)
    assert len(reply) > 0


def test_state_becomes_chat_ready_after_init():
    svc, sm = make_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    svc.process_message(sid, "__init__")
    session = sm.get_session(sid)
    assert session.state == "CHAT_READY"


def test_under_10_path_executes_without_error():
    svc, sm = make_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    sm.update_session(sid, age_bracket="Under 10")
    reply, qr = svc.process_message(sid, "__init__")
    assert isinstance(reply, str)
    assert len(reply) > 0


def test_sessions_are_isolated():
    svc, sm = make_service()
    sid1 = str(uuid.uuid4())
    sid2 = str(uuid.uuid4())
    sm.create_session(sid1)
    sm.create_session(sid2)

    svc.process_message(sid1, "__init__")
    # Advance sid1 further through state machine
    svc.process_message(sid1, "I am in danger or thinking about hurting myself.")

    svc.process_message(sid2, "__init__")

    s1 = sm.get_session(sid1)
    s2 = sm.get_session(sid2)

    # States must differ — sid1 advanced to PICK_HARM, sid2 is CHAT_READY
    assert s1.state != s2.state, (
        f"Sessions should have different states but both have: {s1.state}"
    )
    # Sessions must be independent objects
    assert s1 is not s2
    assert s1.session_id != s2.session_id
