import logging


def post(client, path, **payload):
    return client.post(path, json=payload)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_endpoint_returns_full_contract(client, helpline):
    response = post(client, "/api/chat", message="he threatens to leak my nudes", channel="chat", language="en")
    assert response.status_code == 200
    body = response.json()
    for key in (
        "reply", "severity", "category", "safe_actions", "path_options", "routing",
        "human_review", "confidence", "matched_rules", "helpline_configured",
        "language_fallback", "needs_native_review", "content_review_status",
    ):
        assert key in body
    assert body["severity"] in ("S3", "S4")
    assert helpline in body["reply"]


def test_triage_endpoint_returns_classification_only(client):
    body = post(client, "/api/ai/triage", message="I want to kill myself").json()
    assert body["severity"] == "S4"
    assert body["danger"] is True
    assert "reply" not in body


def test_chat_works_without_helpline_configured(client):
    body = post(client, "/api/chat", message="I want to kill myself").json()
    assert body["helpline_configured"] is False
    assert body["severity"] == "S4"


def test_empty_message_rejected(client):
    assert post(client, "/api/chat", message="").status_code == 422


def test_blank_message_rejected(client):
    assert post(client, "/api/chat", message="   \n ").status_code == 422


def test_missing_message_rejected(client):
    assert client.post("/api/chat", json={}).status_code == 422


def test_overlong_message_rejected(client):
    assert post(client, "/api/chat", message="a" * 2001).status_code == 422


def test_maximum_length_message_accepted(client):
    assert post(client, "/api/chat", message="a" * 2000).status_code == 200


def test_invalid_enum_values_rejected(client):
    assert post(client, "/api/chat", message="hi", language="fr").status_code == 422
    assert post(client, "/api/chat", message="hi", channel="fax").status_code == 422
    assert post(client, "/api/chat", message="hi", category_hint="bogus").status_code == 422


def test_unknown_fields_rejected(client):
    assert post(client, "/api/chat", message="hi", extra_field=1).status_code == 422


def test_malformed_json_rejected(client):
    response = client.post("/api/chat", content=b"{not json", headers={"content-type": "application/json"})
    assert response.status_code == 422


def test_validation_errors_do_not_echo_input(client):
    response = post(client, "/api/chat", message="secret-text-424242", language="fr")
    assert response.status_code == 422
    assert "secret-text-424242" not in response.text


def test_logs_never_contain_message_text(client, caplog):
    caplog.set_level(logging.DEBUG)
    post(client, "/api/chat", message="secret-text-424242 he threatens to leak my nudes")
    post(client, "/api/chat", message="secret-text-424242", language="fr")
    assert "secret-text-424242" not in caplog.text
    assert "assessed severity=" in caplog.text


def test_sms_reply_fits_one_message(client, helpline):
    body = post(client, "/api/chat", message="he threatens to leak my nudes", channel="sms").json()
    assert len(body["reply"]) <= 160


def test_knowledge_search_returns_approved_entry(client):
    body = post(client, "/api/knowledge/search", query="my account got hacked").json()
    assert body["matched"] is True
    assert body["backend"] == "keyword"
    assert body["guidance"]["id"] == "hacked-account"
    assert body["guidance"]["review_status"] == "draft"
    assert body["best_score"] >= 0.3


def test_knowledge_search_with_no_match_hands_over_to_a_person(client):
    body = post(client, "/api/knowledge/search", query="what is the weather in kampala").json()
    assert body["matched"] is False
    assert body["guidance"] is None
    assert body["best_score"] == 0.0


def test_knowledge_search_validation(client):
    assert post(client, "/api/knowledge/search", query="").status_code == 422
    assert post(client, "/api/knowledge/search", query="  ").status_code == 422
    assert post(client, "/api/knowledge/search", query="a" * 501).status_code == 422
    assert post(client, "/api/knowledge/search", query="hi", language="fr").status_code == 422
    assert post(client, "/api/knowledge/search", query="hi", extra=1).status_code == 422


def test_knowledge_search_logs_no_query_text(client, caplog):
    caplog.set_level(logging.DEBUG)
    post(client, "/api/knowledge/search", query="secret-query-515151 my account got hacked")
    assert "secret-query-515151" not in caplog.text
    assert "knowledge search backend=" in caplog.text


def test_chat_attaches_guidance_for_calm_english_chat(client):
    body = post(client, "/api/chat", message="someone hacked my account").json()
    assert body["severity"] == "S2"
    assert body["guidance"]["id"] == "hacked-account"


def test_chat_has_no_guidance_for_danger(client):
    body = post(client, "/api/chat", message="I want to kill myself, my account got hacked").json()
    assert body["severity"] == "S4"
    assert body["guidance"] is None


def test_chat_has_no_guidance_for_s3(client):
    body = post(client, "/api/chat", message="he threatens to leak my nudes if I do not pay").json()
    assert body["severity"] == "S3"
    assert body["guidance"] is None


def test_chat_has_no_guidance_on_sms_or_luganda(client):
    assert post(client, "/api/chat", message="someone hacked my account", channel="sms").json()["guidance"] is None
    assert post(client, "/api/chat", message="someone hacked my account", language="lg").json()["guidance"] is None


def test_chat_survives_retrieval_failure(client, monkeypatch):
    from ai_service.engine import main

    def broken(*_args, **_kwargs):
        raise RuntimeError("index corrupt")

    monkeypatch.setattr(main, "search", broken)
    response = post(client, "/api/chat", message="someone hacked my account")
    assert response.status_code == 200
    assert response.json()["guidance"] is None
