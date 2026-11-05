"""Tests for the conversation state machine."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import pytest
import services.conversation as conv_mod
from services.conversation import ConversationService, HARM_CATEGORIES, HARM_CATEGORIES_SIMPLE
from services.session import SessionManager


def make_isolated_service():
    """Return a ConversationService backed by a fresh, isolated SessionManager."""
    sm = SessionManager()
    # Patch module-level singletons so api_client also sees the right session_manager
    conv_mod.session_manager = sm
    svc = ConversationService()
    return svc, sm


# ── Greeting ───────────────────────────────────────────────────────────────────

def test_init_returns_greeting_and_five_quick_replies():
    svc, sm = make_isolated_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    reply, qr = svc.process_message(sid, "__init__")
    assert isinstance(reply, str) and len(reply) > 0
    assert len(qr) == 5


def test_init_greeting_contains_habari():
    svc, sm = make_isolated_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    reply, _ = svc.process_message(sid, "__init__")
    assert "habari" in reply.lower() or "here" in reply.lower()


def test_state_becomes_chat_ready_after_init():
    svc, sm = make_isolated_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    svc.process_message(sid, "__init__")
    assert sm.get_session(sid).state == "CHAT_READY"


# ── Under-10 path ─────────────────────────────────────────────────────────────

def test_under_10_receives_simple_categories():
    svc, sm = make_isolated_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    sm.update_session(sid, age_bracket="Under 10")
    _, qr = svc.process_message(sid, "__init__")
    assert qr == HARM_CATEGORIES_SIMPLE


def test_under_10_receives_simple_reply_on_category():
    svc, sm = make_isolated_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    sm.update_session(sid, age_bracket="Under 10", state="CHAT_READY")
    reply, _ = svc.process_message(sid, HARM_CATEGORIES_SIMPLE[0])
    assert isinstance(reply, str) and len(reply) > 0


# ── Harm category selection ────────────────────────────────────────────────────

def test_harm_category_sets_pick_harm_state():
    svc, sm = make_isolated_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    svc.process_message(sid, "__init__")
    svc.process_message(sid, HARM_CATEGORIES[0])
    assert sm.get_session(sid).state == "PICK_HARM"


def test_harm_category_stored_on_session():
    svc, sm = make_isolated_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    svc.process_message(sid, "__init__")
    svc.process_message(sid, HARM_CATEGORIES[1])
    assert sm.get_session(sid).harm_category == HARM_CATEGORIES[1]


@pytest.mark.parametrize("cat", HARM_CATEGORIES)
def test_each_harm_category_returns_reply(cat):
    svc, sm = make_isolated_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    svc.process_message(sid, "__init__")
    reply, qr = svc.process_message(sid, cat)
    assert isinstance(reply, str) and len(reply) > 0
    assert isinstance(qr, list)


# ── Multi-turn conversation ────────────────────────────────────────────────────

def test_describe_problem_advances_state():
    """
    Flow: init → harm category (PICK_HARM) → first description (DESCRIBE_PROBLEM)
    → second message (REPORT_REVIEW).
    The service intentionally stays in DESCRIBE_PROBLEM after the first free-text
    message to ask one follow-up question before moving to report review.
    """
    svc, sm = make_isolated_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    svc.process_message(sid, "__init__")
    svc.process_message(sid, HARM_CATEGORIES[2])          # PICK_HARM
    svc.process_message(sid, "He hits me every night")    # DESCRIBE_PROBLEM (follow-up asked)
    assert sm.get_session(sid).state == "DESCRIBE_PROBLEM"
    svc.process_message(sid, "He has been doing this for a year")  # REPORT_REVIEW
    assert sm.get_session(sid).state == "REPORT_REVIEW"


def test_continue_to_report_sets_report_review():
    """
    'Continue to report →' is a special reply that is matched regardless of state.
    It should set state to REPORT_REVIEW.
    Note: the special reply is only in _SPECIAL_REPLIES when state == PICK_HARM or later.
    We advance to DESCRIBE_PROBLEM first so the special reply key is reachable.
    """
    svc, sm = make_isolated_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    svc.process_message(sid, "__init__")
    svc.process_message(sid, HARM_CATEGORIES[0])          # PICK_HARM
    svc.process_message(sid, "I've been feeling this way") # DESCRIBE_PROBLEM
    reply, _ = svc.process_message(sid, "Continue to report →")
    assert sm.get_session(sid).state == "REPORT_REVIEW"


def test_navigate_report_sentinel_returned():
    svc, sm = make_isolated_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    svc.process_message(sid, "__init__")
    svc.process_message(sid, HARM_CATEGORIES[0])
    svc.process_message(sid, "Continue to report →")
    reply, _ = svc.process_message(sid, "Go to report review →")
    assert reply == "__navigate_report__"


def test_navigate_help_sentinel_returned():
    svc, sm = make_isolated_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    svc.process_message(sid, "__init__")
    svc.process_message(sid, HARM_CATEGORIES[0])
    svc.process_message(sid, "I need human support")
    reply, _ = svc.process_message(sid, "Yes, connect me →")
    assert reply == "__navigate_help__"


# ── Session isolation ─────────────────────────────────────────────────────────

def test_sessions_are_isolated():
    svc, sm = make_isolated_service()
    sid1, sid2 = str(uuid.uuid4()), str(uuid.uuid4())
    sm.create_session(sid1)
    sm.create_session(sid2)

    svc.process_message(sid1, "__init__")
    svc.process_message(sid1, HARM_CATEGORIES[0])   # advances sid1 to PICK_HARM

    svc.process_message(sid2, "__init__")            # sid2 stays at CHAT_READY

    s1 = sm.get_session(sid1)
    s2 = sm.get_session(sid2)
    assert s1.state != s2.state
    assert s1.session_id != s2.session_id
    assert s1 is not s2


def test_default_reply_for_unknown_input():
    svc, sm = make_isolated_service()
    sid = str(uuid.uuid4())
    sm.create_session(sid)
    svc.process_message(sid, "__init__")
    reply, qr = svc.process_message(sid, "something completely random xyzzy")
    assert isinstance(reply, str) and len(reply) > 0
    assert isinstance(qr, list)
