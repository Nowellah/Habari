import logging

import pytest
from pydantic import ValidationError

from ai_service.engine.config import Settings
from ai_service.engine.content import REQUIRED_CHOICES, REQUIRED_PROMPTS, is_complete, select_bundle
from ai_service.engine.conversation import MAX_CLARIFY, _pack, take_turn
from ai_service.engine.schemas import ConversationState, TurnRequest

WITH_HELPLINE = Settings(helpline_number="0800 100 200")
NO_HELPLINE = Settings(helpline_number=None)


def turn(state=None, settings=WITH_HELPLINE, **kwargs):
    return take_turn(TurnRequest(state=state, **kwargs), settings)


def calm_offer_state(settings=WITH_HELPLINE, channel="chat"):
    response = turn(text="I saw something disturbing online", settings=settings, channel=channel)
    return turn(response.state, choice="feel_little", settings=settings, channel=channel).state


def ids(response):
    return [c.id for c in response.choices]


def texts(response):
    return " ".join((m.text or "") + " ".join(m.items or []) for m in response.messages)


def test_flow_content_is_complete_in_english():
    bundle = select_bundle("en")[0]
    assert is_complete(bundle)
    assert all(key in bundle["flow"]["prompts"] for key in REQUIRED_PROMPTS)
    assert all(key in bundle["flow"]["choices"] for key in REQUIRED_CHOICES)


def test_start_greets_and_waits_for_the_childs_words():
    response = turn()
    assert response.state.step == "describe"
    assert response.accepts_text is True and response.choices == []
    assert "Mukwano" in response.messages[0].text and "automated" in response.messages[0].text


def test_calm_message_asks_how_it_feels_then_offers_options_without_more_questions():
    response = turn(text="I saw something disturbing online")
    assert response.state.step == "ask_feeling"
    assert ids(response) == ["feel_little", "feel_lot", "feel_scared", "feel_danger", "feel_skip"]
    response = turn(response.state, choice="feel_little")
    assert response.state.step == "offer"
    assert ids(response) == ["talk_to_person", "report_privately", "keep_proof", "just_information", "done"]


def test_unclear_message_asks_for_more_then_proceeds_after_limit():
    response = turn(text="something happened at the thing yesterday")
    assert response.state.step == "describe" and response.state.clarify_count == 1
    for _ in range(MAX_CLARIFY):
        response = turn(response.state, text="something happened at the thing yesterday")
    assert response.state.step != "describe"
    assert response.assessment.confidence == "low"
    assert response.assessment.human_review is True


def test_serious_case_asks_now_then_who_then_offers():
    response = turn(text="he threatens to leak my nudes")
    assert response.state.step == "ask_feeling"
    response = turn(response.state, choice="feel_skip")
    assert response.state.step == "ask_now" and ids(response) == ["yes", "no", "not_sure"]
    response = turn(response.state, choice="yes")
    assert response.state.step == "ask_who" and "teacher" in ids(response)
    response = turn(response.state, choice="stranger")
    assert response.state.step == "offer"
    assert response.assessment.severity.value == "S3"


def test_happening_now_raises_s2_to_s3():
    response = turn(text="people keep laughing at me in the group chat")
    response = turn(response.state, choice="feel_skip")
    assert response.assessment.severity.value == "S2"
    response = turn(response.state, choice="yes")
    assert response.assessment.severity.value == "S3"
    assert "happening_now" in response.assessment.matched_rules


def test_trusted_adult_keeps_family_and_school_out_and_tells_the_child():
    response = turn(text="he threatens to leak my nudes")
    response = turn(response.state, choice="feel_skip")
    response = turn(response.state, choice="no")
    response = turn(response.state, choice="family")
    assert response.assessment.external_only is True
    assert "family_or_school" not in response.routing.allowed_routes
    assert "won't share this with your family or school" in texts(response)


def test_text_naming_a_parent_is_external_only_from_the_first_turn():
    response = turn(text="my stepfather hits me")
    assert response.assessment.external_only is True


def test_danger_goes_straight_to_a_safety_check_with_the_helpline():
    response = turn(text="I want to kill myself")
    assert response.state.step == "danger_check" and ids(response) == ["safe_yes", "safe_no"]
    assert response.assessment.severity.value == "S4"
    assert response.messages[0].kind == "danger"
    assert "0800 100 200" in response.messages[0].text
    assert response.routing.human_decision_required is True


def test_danger_typed_at_any_step_interrupts_the_flow():
    state = calm_offer_state()
    assert state.step == "offer"
    response = turn(state, text="he is outside my door")
    assert response.state.step == "danger_check"
    assert response.assessment.severity.value == "S4"


def test_danger_typed_while_answering_a_menu_is_not_lost():
    state = turn(text="he threatens to leak my nudes").state
    response = turn(state, text="i want to kill myself")
    assert response.state.step == "danger_check"


def test_not_safe_repeats_help_and_stays_on_the_check():
    response = turn(text="I want to kill myself")
    response = turn(response.state, choice="safe_no")
    assert response.state.step == "danger_check"
    assert "safe place" in texts(response) and "0800 100 200" in texts(response)
    response = turn(response.state, choice="safe_yes")
    assert response.state.step == "offer"


def test_the_danger_button_hint_starts_in_danger():
    response = turn(text="I need help now", category_hint="immediate_danger")
    assert response.state.step == "danger_check" or response.assessment.severity.value == "S4"
    assert response.assessment.severity.value == "S4"


def test_severity_never_goes_down():
    state = ConversationState(step="describe", severity="S3", category="sextortion", narrative=["x"])
    response = turn(state, text="actually it is fine, I am just talking")
    assert response.assessment.severity.value == "S3"
    assert response.assessment.category.value == "sextortion"


def test_a_lowered_severity_in_a_tampered_state_is_recomputed_from_the_words():
    state = ConversationState(step="offer", severity="S1", narrative=["he threatens to leak my nudes"])
    response = turn(state, choice="report_privately")
    assert response.state.step == "report_review"
    state2 = ConversationState(step="describe", severity="S1", narrative=["he threatens to leak my nudes"])
    assert turn(state2, text="ok").assessment.severity.value == "S3"


def test_offer_talk_to_person_gives_the_helpline_and_stays_on_the_menu():
    state = calm_offer_state()
    response = turn(state, choice="talk_to_person")
    assert "0800 100 200" in texts(response) and response.state.step == "offer"


def test_offer_talk_to_person_without_a_helpline_still_helps():
    state = calm_offer_state(settings=NO_HELPLINE)
    response = turn(state, choice="talk_to_person", settings=NO_HELPLINE)
    assert "adult you trust" in texts(response)
    assert response.helpline_configured is False


def test_keep_proof_returns_approved_guidance():
    state = calm_offer_state()
    response = turn(state, choice="keep_proof")
    assert response.messages[0].kind == "guidance"
    assert "Don't delete the messages" in response.messages[0].text


def test_ask_a_question_returns_approved_answer_or_hands_over_to_a_person():
    state = calm_offer_state()
    response = turn(state, choice="just_information")
    assert response.state.step == "ask_question"
    answered = turn(response.state, text="how do I block a person")
    assert answered.messages[0].kind == "guidance" and answered.state.step == "offer"
    missed = turn(response.state, text="what is the weather in kampala")
    assert "trained person can help" in texts(missed) and "0800 100 200" in texts(missed)


def test_done_ends_the_conversation():
    state = calm_offer_state()
    response = turn(state, choice="done")
    assert response.ended is True and response.accepts_text is False
    assert turn(response.state, text="more").ended is True


def _to_review(text="my teacher keeps touching me"):
    response = turn(text=text)
    answers = {"ask_feeling": "feel_skip", "ask_now": "no", "ask_who": "teacher"}
    while response.state.step in answers:
        response = turn(response.state, choice=answers[response.state.step])
    return turn(response.state, choice="report_privately")


def test_report_review_shows_what_would_be_shared_and_asks_before_preparing():
    response = _to_review()
    assert response.state.step == "report_review" and ids(response) == ["confirm_send", "edit", "not_now"]
    shown = texts(response)
    assert "Nothing is sent unless you say yes" in shown
    assert "my teacher keeps touching me" in shown
    assert response.case_draft is None


def test_confirming_prepares_a_draft_only_after_consent():
    response = turn(_to_review().state, choice="confirm_send")
    draft = response.case_draft
    assert draft.consent_confirmed is True
    assert draft.summary == "my teacher keeps touching me"
    assert draft.external_only is True and draft.human_review is True
    assert draft.severity.value == "S3" and draft.category.value == "abuse"
    assert "family_or_school" not in draft.allowed_routes
    assert response.ended is True


def test_not_now_returns_to_the_options_without_a_draft():
    response = turn(_to_review().state, choice="not_now")
    assert response.state.step == "offer" and response.case_draft is None


def test_edit_adds_words_and_shows_the_review_again():
    response = turn(_to_review().state, choice="edit")
    assert response.state.step == "edit"
    response = turn(response.state, text="it happened after class")
    assert response.state.step == "report_review"
    assert "after class" in texts(response)
    confirmed = turn(response.state, choice="confirm_send")
    assert "after class" in confirmed.case_draft.summary


def test_invalid_choice_asks_again_on_the_same_step():
    state = turn(text="he threatens to leak my nudes").state
    response = turn(state, choice="banana")
    assert response.state.step == state.step
    assert "choose one" in texts(response)


def test_a_menu_number_works_as_a_choice():
    state = turn(text="he threatens to leak my nudes", channel="sms").state
    assert state.step == "ask_feeling"
    response = turn(state, text="1", channel="sms")
    assert response.state.self_rating == "feel_little"


def test_unmatched_text_at_a_menu_asks_again_and_keeps_the_words():
    state = turn(text="he threatens to leak my nudes").state
    response = turn(state, text="he also called me")
    assert response.state.step == "ask_feeling"
    assert len(response.state.narrative) == 2


@pytest.mark.parametrize("channel", ["sms", "ussd"])
@pytest.mark.parametrize("settings", [WITH_HELPLINE, NO_HELPLINE])
def test_short_channels_keep_every_screen_within_160_characters(channel, settings):
    steps = [
        dict(text="my teacher keeps touching me"),
        dict(choice="feel_skip"), dict(choice="yes"), dict(choice="talk_to_person"),
        dict(choice="keep_proof"), dict(choice="just_information"),
        dict(text="someone hacked my account"), dict(choice="report_privately"),
        dict(choice="edit"), dict(text="it was after class and I am afraid"),
        dict(choice="confirm_send"),
    ]
    response = turn(settings=settings, channel=channel)
    for step in steps:
        response = turn(response.state, settings=settings, channel=channel, **step)
        for message in response.messages:
            assert len(message.text) <= 160, message.text
        if response.menu_text:
            assert len(response.menu_text) <= 160
            assert len(response.messages[-1].text + "\n" + response.menu_text) <= 160, (
                response.messages[-1].text, response.menu_text)
    assert response.ended is True


def test_short_channel_shows_a_numbered_menu():
    response = turn(text="he threatens to leak my nudes", channel="ussd")
    assert response.menu_text == "1. A little 2. A lot 3. Scared 4. In danger 5. Skip"
    response = turn(response.state, choice="feel_skip", channel="ussd")
    assert response.menu_text == "1. Yes 2. No 3. Unsure"


def test_short_report_review_does_not_echo_the_childs_words():
    state = turn(text="my teacher keeps touching me", channel="sms").state
    state = turn(state, choice="feel_skip", channel="sms").state
    state = turn(state, choice="no", channel="sms").state
    response = turn(state, choice="report_privately", channel="sms")
    assert "touching" not in texts(response)


def test_pack_splits_long_text_without_losing_words():
    text = "One short sentence. " + "word " * 80 + "Final sentence here."
    parts = _pack(text, 160)
    assert all(len(p) <= 160 for p in parts)
    assert " ".join(" ".join(parts).split()) == " ".join(text.split())


def test_luganda_request_falls_back_to_english_and_says_so():
    response = turn(text="nsobeddwa nnyo", language="lg")
    assert response.language_used == "en" and response.needs_native_review is True
    assert response.assessment.severity.value == "S3"


def test_state_validation_rejects_bad_input():
    with pytest.raises(ValidationError):
        TurnRequest(text="hi", choice="yes")
    with pytest.raises(ValidationError):
        TurnRequest(text="   ")
    with pytest.raises(ValidationError):
        ConversationState(step="hack")
    with pytest.raises(ValidationError):
        ConversationState(narrative=["a"] * 6)
    with pytest.raises(ValidationError):
        ConversationState(narrative=["a" * 2001])
    with pytest.raises(ValidationError):
        ConversationState(unknown_field=1)


def test_the_state_never_contains_anything_the_child_did_not_write_or_choose():
    response = turn(text="he threatens to leak my nudes")
    dumped = response.state.model_dump()
    assert set(dumped) == set(ConversationState.model_fields)
    assert dumped["narrative"] == ["he threatens to leak my nudes"]


def post(client, **payload):
    return client.post("/api/conversation/turn", json=payload)


def test_api_walks_a_conversation(client, helpline):
    first = post(client).json()
    assert first["state"]["step"] == "describe"
    second = post(client, state=first["state"], text="he threatens to leak my nudes").json()
    assert second["state"]["step"] == "ask_feeling"
    second = post(client, state=second["state"], choice="feel_skip").json()
    assert second["state"]["step"] == "ask_now"
    third = post(client, state=second["state"], choice="no").json()
    assert third["state"]["step"] == "ask_who"
    assert third["case_draft"] is None


def test_api_rejects_tampered_or_oversized_state(client):
    assert post(client, state={"step": "hack"}).status_code == 422
    assert post(client, state={"narrative": ["a"] * 6}).status_code == 422
    assert post(client, state={"extra": 1}).status_code == 422
    assert post(client, text="hi", choice="yes").status_code == 422
    assert post(client, text="").status_code == 422


def test_api_logs_no_words_or_state(client, caplog):
    caplog.set_level(logging.DEBUG)
    post(client, text="secret-words-717171 he threatens to leak my nudes")
    assert "secret-words-717171" not in caplog.text
    assert "turn step=" in caplog.text


def _rated(text, rating, **kwargs):
    response = turn(text=text, **kwargs)
    assert response.state.step == "ask_feeling"
    return turn(response.state, choice=rating, **kwargs)


@pytest.mark.parametrize("rating,expected", [("feel_little", "S1"), ("feel_skip", "S1"), ("feel_lot", "S2"), ("feel_scared", "S3")])
def test_the_childs_rating_sets_a_floor_for_a_calm_report(rating, expected):
    response = _rated("I saw something disturbing online", rating)
    assert response.assessment.severity.value == expected
    assert f"child_rated_{rating.removeprefix('feel_')}" in response.assessment.matched_rules


def test_rating_scared_is_treated_as_serious_for_any_category():
    response = _rated("someone is making fun of me online", "feel_scared")
    assert response.assessment.severity.value == "S3"
    assert response.assessment.human_review is True
    assert response.state.step == "ask_now"


def test_a_low_rating_never_lowers_what_the_system_found():
    response = _rated("he threatens to leak my nudes", "feel_little")
    assert response.assessment.severity.value == "S3"
    assert "may feel small" in texts(response)


def test_a_low_rating_on_a_calm_report_gets_no_correction():
    response = _rated("I saw something disturbing online", "feel_little")
    assert "may feel small" not in texts(response)


def test_in_danger_rating_goes_to_the_safety_check():
    response = _rated("someone is making fun of me online", "feel_danger")
    assert response.state.step == "danger_check"
    assert response.assessment.severity.value == "S4"
    assert response.routing.human_decision_required is True
    assert "0800 100 200" in texts(response)


def test_the_rating_persists_and_is_asked_only_once():
    response = _rated("I saw something disturbing online", "feel_scared")
    response = turn(response.state, choice="no")
    assert response.state.step in ("ask_who", "offer")
    response = turn(response.state, choice="report_privately") if response.state.step == "offer" else response
    assert response.state.self_rating == "feel_scared" and response.state.asked_feeling is True
    assert response.assessment.severity.value == "S3"


def test_the_rating_drives_what_happens_next():
    calm = _rated("I saw something disturbing online", "feel_little")
    scared = _rated("I saw something disturbing online", "feel_scared")
    assert calm.state.step == "offer"
    assert scared.state.step == "ask_now"
    assert scared.routing.allowed_routes != calm.routing.allowed_routes


def test_rating_choices_are_short_enough_for_ussd():
    response = turn(text="I saw something disturbing online", channel="ussd")
    assert response.menu_text == "1. A little 2. A lot 3. Scared 4. In danger 5. Skip"
    assert len(response.messages[-1].text + "\n" + response.menu_text) <= 160


def test_a_tampered_rating_is_rejected():
    with pytest.raises(ValidationError):
        ConversationState(self_rating="feel_nothing")


def test_who_question_is_skipped_when_the_words_already_name_a_trusted_adult():
    response = turn(text="my teacher keeps touching me")
    response = turn(response.state, choice="feel_skip")
    response = turn(response.state, choice="no")
    assert response.state.step == "offer"
    assert response.assessment.external_only is True


def test_who_question_is_still_asked_when_nobody_is_named():
    response = turn(text="he threatens to leak my nudes")
    response = turn(response.state, choice="feel_skip")
    response = turn(response.state, choice="no")
    assert response.state.step == "ask_who"
