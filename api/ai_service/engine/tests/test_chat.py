import json

import pytest

from ai_service.engine import content
from ai_service.engine.chat import SHORT_MESSAGE_LIMIT, build_chat_response
from ai_service.engine.config import Settings, get_settings
from ai_service.engine.schemas import Category, MessageRequest
from ai_service.engine.triage import triage

SAFE_ACTION_IDS = ["stop_replying", "do_not_send_money", "keep_messages"]
REALISTIC_HELPLINES = ["116", "0800 100 200", "+256 800 100 200"]


def respond(message, helpline_number="0800 100 200", **kwargs):
    request = MessageRequest(message=message, **kwargs)
    result = triage(
        request.message,
        language=request.language,
        happening_now=request.happening_now,
        alleged_role=request.alleged_role,
        category_hint=request.category_hint,
    )
    return build_chat_response(request, result, Settings(helpline_number=helpline_number))


def test_english_bundle_is_complete_and_flagged_as_draft():
    bundle = content.select_bundle("en")[0]
    assert content.is_complete(bundle)
    assert bundle["meta"]["review_status"] == "draft"


def test_every_category_has_a_template():
    bundle = content.select_bundle("en")[0]
    for category in Category:
        assert category.value in bundle["categories"]


@pytest.mark.parametrize("hint", [c.value for c in Category])
@pytest.mark.parametrize("helpline_number", REALISTIC_HELPLINES + [None])
@pytest.mark.parametrize("role", [None, "family"])
def test_short_replies_fit_one_sms_for_every_category(hint, helpline_number, role):
    for channel in ("sms", "ussd"):
        response = respond("hello", helpline_number, channel=channel, category_hint=hint, alleged_role=role)
        assert len(response.reply) <= SHORT_MESSAGE_LIMIT, response.reply


def test_short_reply_keeps_helpline_even_with_a_long_number():
    response = respond("he threatens to leak my nudes", "+256 800 100 200 300", channel="sms", alleged_role="family")
    assert len(response.reply) <= SHORT_MESSAGE_LIMIT
    assert "+256 800 100 200 300" in response.reply


def test_three_safe_actions_always_present():
    for message in ["I want to kill myself", "hello", "he threatens to leak my nudes", "my teacher hits me"]:
        response = respond(message)
        assert [a.id for a in response.safe_actions] == SAFE_ACTION_IDS


def test_chat_reply_discloses_automation_and_offers_a_person():
    response = respond("he threatens to leak my nudes")
    assert "automated helper" in response.reply
    assert "real person" in response.reply


def test_short_reply_discloses_automation():
    response = respond("he threatens to leak my nudes", channel="sms")
    assert "auto-reply" in response.reply


def test_danger_reply_leads_with_help_not_disclosure():
    response = respond("I want to kill myself")
    assert response.reply.startswith("I'm really glad you told me")
    assert response.clarifying_question is None
    assert response.routing.human_decision_required is True
    assert response.path_options[0].id == "talk_to_person"
    assert len(response.path_options) == 1


def test_helpline_comes_from_configuration():
    response = respond("he threatens to leak my nudes", "0800 777 888")
    assert "0800 777 888" in response.reply
    assert response.helpline == "0800 777 888"
    assert response.helpline_configured is True


def test_missing_helpline_is_flagged_and_reply_still_helps():
    response = respond("I want to kill myself", None)
    assert response.helpline_configured is False
    assert response.helpline is None
    assert "adult you trust" in response.reply


def test_invalid_helpline_setting_is_ignored(monkeypatch):
    monkeypatch.setenv("HABARI_HELPLINE_NUMBER", "call <script>")
    assert get_settings().helpline_number is None


def test_external_only_removes_family_or_school_route_and_adds_note():
    response = respond("my teacher keeps touching me")
    assert response.routing.external_only is True
    assert "family_or_school" not in response.routing.allowed_routes
    assert "child_protection_partner" in response.routing.allowed_routes
    assert "family or school" in response.reply


def test_non_external_case_keeps_family_or_school_route():
    response = respond("he asked me to send pictures")
    assert "family_or_school" in response.routing.allowed_routes


def test_replies_never_blame_the_child():
    blame_words = ["your fault", "you should not have", "why did you"]
    for message in ["he threatens to leak my nudes", "he asked me to send pictures", "I got scammed"]:
        reply = respond(message).reply.lower()
        assert not any(word in reply.replace("not your fault", "") for word in blame_words)


def test_reply_does_not_echo_the_message():
    response = respond("unique-marker-998877 he threatens to leak my nudes")
    assert "unique-marker-998877" not in response.model_dump_json()


def test_luganda_falls_back_to_english_and_asks_for_review():
    response = respond("nsobeddwa nnyo", language="lg")
    assert response.language_used == "en"
    assert response.language_fallback is True
    assert response.needs_native_review is True


def test_english_request_needs_no_native_review():
    response = respond("hello")
    assert response.needs_native_review is False
    assert response.language_fallback is False


def _luganda_bundle(status):
    bundle = json.loads(json.dumps(content.select_bundle("en")[0]))
    bundle["meta"] = {"language": "lg", "review_status": status}
    return bundle


def test_approved_complete_luganda_bundle_is_used(monkeypatch):
    approved = _luganda_bundle("approved")
    original = content._load
    monkeypatch.setattr(content, "_load", lambda lang: approved if lang == "lg" else original(lang))
    response = respond("hello", language="lg")
    assert response.language_used == "lg"
    assert response.needs_native_review is False


def test_unapproved_luganda_bundle_is_not_used(monkeypatch):
    draft = _luganda_bundle("draft")
    original = content._load
    monkeypatch.setattr(content, "_load", lambda lang: draft if lang == "lg" else original(lang))
    response = respond("hello", language="lg")
    assert response.language_used == "en"
    assert response.needs_native_review is True


def test_incomplete_luganda_bundle_is_not_used(monkeypatch):
    partial = _luganda_bundle("approved")
    del partial["categories"]["abuse"]
    original = content._load
    monkeypatch.setattr(content, "_load", lambda lang: partial if lang == "lg" else original(lang))
    assert respond("hello", language="lg").language_used == "en"


def test_clarifying_question_present_when_unclear():
    response = respond("something happened at the thing yesterday")
    assert response.clarifying_question
    assert response.human_review is True
