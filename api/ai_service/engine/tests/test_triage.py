import pytest

from ai_service.engine import triage as triage_module
from ai_service.engine.schemas import Category, Severity
from ai_service.engine.triage import safe_triage, triage

DANGER_MESSAGES = [
    "I want to kill myself",
    "i dont want to live anymore",
    "I don't want to live anymore",
    "I DON'T WANT TO LIVE",
    "thinking about suicide",
    "I want to end my life",
    "i wish i was dead",
    "I want to diiiiie because I want to die",
    "he is outside my door",
    "he said he will kill me",
    "my uncle is beating me right now",
    "\U0001F198",
    "\U0001F6A8 help",
    "I think i should hurt myself",
    "nobody would notice if i was gone",
    "no one would miss me",
    "everyone is better off without me",
    "i want to disappear forever",
    "i dont want to wake up",
    "i dont want to go on like this",
]

HARMLESS_LOOKALIKES = [
    "nobody would believe my story",
    "i cant go on holiday this year",
    "i want to disappear from the group chat",
    "my sister is better off at the new school",
]


@pytest.mark.parametrize("message", DANGER_MESSAGES)
def test_danger_phrases_are_always_s4(message):
    result = triage(message)
    assert result.severity == Severity.S4
    assert result.danger is True
    assert result.human_review is True
    assert result.needs_clarification is False


def test_self_harm_category_wins_over_other_danger_category():
    result = triage("I want to kill myself, he is outside my door")
    assert result.category == Category.SELF_HARM


@pytest.mark.parametrize("hint", ["self_harm", "immediate_danger"])
def test_danger_hint_alone_is_s4(hint):
    result = triage("hello", category_hint=hint)
    assert result.severity == Severity.S4


@pytest.mark.parametrize(
    "message",
    [
        "he is going to leak my nudes",
        "someone is blackmailing me with my photos",
        "he said he will post my pictures if I do not pay",
        "he asked me for money or he shares my photos",
        "this is sextortion",
    ],
)
def test_sextortion_is_at_least_s3(message):
    result = triage(message)
    assert result.category == Category.SEXTORTION
    assert result.severity.rank >= 3
    assert result.human_review is True


def test_payment_demand_with_images_is_flagged():
    result = triage("he asked me to pay airtime for my photos")
    assert "sextortion_payment_demand" in result.matched_rules
    assert result.severity.rank >= 3


@pytest.mark.parametrize(
    "message,role",
    [
        ("my teacher keeps touching me", None),
        ("my stepfather hits me", None),
        ("someone is hurting me", "guardian"),
        ("he hit me", "family"),
        ("I am scared of him", "teacher"),
    ],
)
def test_trusted_adult_is_at_least_s3_and_external_only(message, role):
    result = triage(message, alleged_role=role)
    assert result.severity.rank >= 3
    assert result.external_only is True
    assert result.human_review is True
    assert "trusted_adult_involved" in result.matched_rules


def test_trusted_adult_without_any_harm_signal_is_not_escalated():
    result = triage("my teacher gave us a new subject today", alleged_role=None)
    assert result.external_only is False
    assert "trusted_adult_involved" not in result.matched_rules


def test_context_role_with_neutral_greeting_does_not_escalate():
    result = triage("hello", alleged_role="family")
    assert result.severity == Severity.S1
    assert result.external_only is False


def test_stranger_role_does_not_set_external_only():
    result = triage("an older man asked me to send pictures", alleged_role="stranger")
    assert result.external_only is False


def test_grooming_meetup_is_s3():
    result = triage("he wants me to meet him alone")
    assert result.category == Category.GROOMING
    assert result.severity == Severity.S3


def test_grooming_images_request_is_s2():
    result = triage("he asked me to send pictures of me")
    assert result.category == Category.GROOMING
    assert result.severity == Severity.S2


def test_unclear_message_goes_one_level_up_with_question_and_review():
    result = triage("something happened at the thing yesterday")
    assert result.severity == Severity.S2
    assert result.confidence == "low"
    assert result.needs_clarification is True
    assert result.human_review is True


def test_short_unmatched_message_is_s1_but_asks_a_question():
    result = triage("ok")
    assert result.severity == Severity.S1
    assert result.needs_clarification is True


def test_greeting_is_s1_and_welcomed_with_a_question():
    result = triage("Hello!")
    assert result.severity == Severity.S1
    assert result.needs_clarification is True


def test_help_request_is_not_treated_as_safe():
    result = triage("help")
    assert result.severity.rank >= 2


def test_hint_and_text_combine_and_higher_wins():
    text_only = triage("I saw something disturbing")
    combined = triage("I saw something disturbing", category_hint="sextortion")
    assert text_only.severity == Severity.S1
    assert combined.severity == Severity.S3
    assert combined.category == Category.SEXTORTION

    text_high = triage("he threatens to leak my nudes", category_hint="exposure")
    assert text_high.severity.rank >= 3
    assert text_high.category == Category.SEXTORTION


def test_happening_now_raises_s2_to_s3():
    calm = triage("he asked me to send pictures", happening_now=False)
    urgent = triage("he asked me to send pictures", happening_now=True)
    assert calm.severity == Severity.S2
    assert urgent.severity == Severity.S3


@pytest.mark.parametrize("language", ["lg"])
def test_unassessable_language_is_s3_with_review(language):
    result = triage("nsobeddwa nnyo ku mukutu", language=language)
    assert result.severity == Severity.S3
    assert result.human_review is True
    assert "language_not_assessable" in result.matched_rules


def test_danger_in_english_inside_lg_request_still_wins():
    assert triage("i want to kill myself", language="lg").severity == Severity.S4


def test_severity_never_lowered_by_hint():
    assert triage("he is outside my door", category_hint="exposure").severity == Severity.S4


def test_result_contains_no_message_text():
    secret = "zebra-token-12345 he threatens to leak my nudes"
    dumped = triage(secret).model_dump_json()
    assert "zebra-token-12345" not in dumped


def test_repeated_calls_are_stateless():
    first = triage("he threatens to leak my nudes")
    triage("I want to kill myself")
    assert triage("he threatens to leak my nudes") == first


def test_large_input_is_handled_quickly():
    message = ("this is a normal sentence about school and friends " * 40)[:2000]
    assert triage(message).severity.rank >= 1


def test_unicode_and_emoji_do_not_break_triage():
    assert triage("مرحبا \U0001F600 ​​").severity.rank >= 1


def test_degraded_mode_still_catches_danger(monkeypatch):
    def broken(_text):
        raise ValueError("boom")

    monkeypatch.setattr(triage_module, "_text_signals", broken)
    danger = safe_triage("I want to kill myself")
    assert danger.severity == Severity.S4
    assert "triage_degraded" in danger.matched_rules


def test_degraded_mode_defaults_to_s3_for_everything_else(monkeypatch):
    def broken(_text):
        raise ValueError("boom")

    monkeypatch.setattr(triage_module, "_text_signals", broken)
    result = safe_triage("something about school")
    assert result.severity == Severity.S3
    assert result.human_review is True


@pytest.mark.parametrize(
    "message",
    [
        "someone is making fun of me online",
        "they keep teasing me in the group",
        "the girls call me names every day",
        "they made fun of my picture",
    ],
)
def test_common_bullying_phrasings_are_recognised(message):
    result = triage(message)
    assert result.category == Category.HARASSMENT
    assert result.severity == Severity.S2


@pytest.mark.parametrize("message", HARMLESS_LOOKALIKES)
def test_harmless_lookalikes_are_not_critical(message):
    assert triage(message).severity != Severity.S4
