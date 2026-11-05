import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.safety import SafetyService

safety = SafetyService()


def test_self_harm_urgent():
    result = safety.check_urgency("I want to kill myself")
    assert result["urgent"] is True
    assert result["severity"] == "critical"


def test_sexual_exploitation_urgent():
    result = safety.check_urgency("Someone wants to see my naked pictures")
    assert result["urgent"] is True


def test_safe_message_not_urgent():
    result = safety.check_urgency("I had a nice day at school today")
    assert result["urgent"] is False
    assert result["severity"] != "critical"


def test_empty_string_not_urgent():
    result = safety.check_urgency("")
    assert result["urgent"] is False


def test_mixed_case_urgent():
    result = safety.check_urgency("I WANT TO DIE")
    assert result["urgent"] is True


def test_emergency_guidance_helpline():
    guidance = safety.get_emergency_guidance("en")
    assert guidance["helpline"] == "116"
    assert "message" in guidance
    assert "language" in guidance


def test_emergency_guidance_default_language():
    """Unknown language code falls back to English message."""
    guidance = safety.get_emergency_guidance("xx")
    assert guidance["helpline"] == "116"
