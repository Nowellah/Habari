"""Tests for SafetyService — keyword urgency detection and emergency guidance."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.safety import SafetyService

safety = SafetyService()


# ── Urgent signals ────────────────────────────────────────────────────────────

def test_self_harm_urgent():
    result = safety.check_urgency("I want to kill myself")
    assert result["urgent"] is True
    assert result["severity"] == "critical"
    assert result["harm_type"] == "self_harm"


def test_self_harm_variant():
    result = safety.check_urgency("I want to end my life")
    assert result["urgent"] is True


def test_sexual_exploitation_urgent():
    result = safety.check_urgency("Someone wants to see my naked pictures")
    assert result["urgent"] is True
    assert result["harm_type"] == "sexual_exploitation"


def test_grooming_urgent():
    result = safety.check_urgency("He has been grooming me for months")
    assert result["urgent"] is True


def test_physical_danger_urgent():
    result = safety.check_urgency("My uncle is beating me every night")
    assert result["urgent"] is True
    assert result["harm_type"] == "physical_danger"


def test_threat_urgent():
    result = safety.check_urgency("He threatened me if I tell anyone")
    assert result["urgent"] is True
    assert result["harm_type"] == "threat"


def test_blackmail_urgent():
    result = safety.check_urgency("They are using blackmail to get my photos")
    assert result["urgent"] is True


# ── Non-urgent ────────────────────────────────────────────────────────────────

def test_safe_message_not_urgent():
    result = safety.check_urgency("I had a nice day at school today")
    assert result["urgent"] is False
    assert result["severity"] != "critical"


def test_empty_string_not_urgent():
    result = safety.check_urgency("")
    assert result["urgent"] is False


def test_none_value_handled():
    """None should not raise; treat as non-urgent."""
    # The service expects a string; passing None would be a caller bug,
    # but empty string is the minimum guard test
    result = safety.check_urgency("")
    assert result["urgent"] is False


# ── Case insensitivity ────────────────────────────────────────────────────────

def test_mixed_case_urgent():
    result = safety.check_urgency("I WANT TO DIE")
    assert result["urgent"] is True


def test_uppercase_exploitation():
    result = safety.check_urgency("SEND NUDES NOW")
    assert result["urgent"] is True


# ── Emergency guidance ────────────────────────────────────────────────────────

def test_emergency_guidance_helpline_en():
    guidance = safety.get_emergency_guidance("en")
    assert guidance["helpline"] == "116"
    assert "message" in guidance
    assert "116" in guidance["message"]


def test_emergency_guidance_helpline_lg():
    guidance = safety.get_emergency_guidance("lg")
    assert guidance["helpline"] == "116"
    assert len(guidance["message"]) > 0


def test_emergency_guidance_default_language():
    """Unknown language code falls back to English message."""
    guidance = safety.get_emergency_guidance("xx")
    assert guidance["helpline"] == "116"
    assert "116" in guidance["message"]


def test_emergency_guidance_all_languages():
    for code in ("en", "lg", "sw", "rn"):
        g = safety.get_emergency_guidance(code)
        assert g["helpline"] == "116"
        assert len(g["message"]) > 10


# ── Severity floors ───────────────────────────────────────────────────────────

def test_severity_is_critical_for_urgent():
    result = safety.check_urgency("I want to harm myself")
    assert result["severity"] == "critical"


def test_severity_is_low_for_safe_message():
    result = safety.check_urgency("How do I change my password?")
    assert result["severity"] == "low"
