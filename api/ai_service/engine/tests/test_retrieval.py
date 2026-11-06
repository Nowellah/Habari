import hashlib
import math

import pytest

from ai_service.engine import retrieval
from ai_service.engine.config import Settings, get_settings
from ai_service.engine.retrieval import load_knowledge_base, parse_knowledge_base, search

KEYWORD_SETTINGS = Settings()
EMBED_SETTINGS = Settings(ollama_url="http://127.0.0.1:11434")

EXPECTED_MATCHES = [
    ("he says he will post my nudes if I dont pay", "sextortion-should-i-pay"),
    ("how do I block a person", "block-and-report"),
    ("someone is making fun of me in whatsapp group", "cyberbullying-what-to-do"),
    ("my account got hacked", "hacked-account"),
    ("I won a prize and they want a fee", "scam-prize-message"),
    ("he wants to meet me alone", "meeting-online-friend"),
    ("he asked me for pictures of my body", "asked-for-photos"),
    ("a stranger asked where I live", "personal-information"),
    ("is it ok to delete the chat", "deleted-messages"),
    ("my friend is being blackmailed", "friend-needs-help"),
    ("I want to remove a picture someone posted of me", "photo-shared-without-consent"),
]
UNRELATED_QUERIES = ["what is the weather in kampala", "tell me a joke", "football scores today", "asdf qwer zxcv", "hello"]


def test_knowledge_base_is_valid_and_marked_draft():
    kb = load_knowledge_base("en")
    assert kb is not None
    assert len(kb.entries) >= 25
    assert kb.review_status == "draft"
    assert len({e.id for e in kb.entries}) == len(kb.entries)
    assert all(len(e.answer) <= retrieval.MAX_ANSWER_LENGTH for e in kb.entries)


def test_no_knowledge_base_exists_for_unreviewed_language():
    assert load_knowledge_base("lg") is None
    result = search("someone hacked my account", "lg", KEYWORD_SETTINGS)
    assert result.match is None and result.backend == "none"


@pytest.mark.parametrize("query,expected", EXPECTED_MATCHES)
def test_keyword_backend_finds_the_expected_entry(query, expected):
    result = search(query, "en", KEYWORD_SETTINGS)
    assert result.backend == "keyword"
    assert result.match is not None and result.match.entry.id == expected


@pytest.mark.parametrize("query", UNRELATED_QUERIES)
def test_unrelated_queries_return_no_match(query):
    assert search(query, "en", KEYWORD_SETTINGS).match is None


def test_matched_text_is_exactly_the_approved_answer():
    kb = load_knowledge_base("en")
    approved = {e.id: e.answer for e in kb.entries}
    for query, expected in EXPECTED_MATCHES:
        match = search(query, "en", KEYWORD_SETTINGS).match
        assert match.entry.answer == approved[match.entry.id]


def test_threshold_can_be_raised_by_configuration(monkeypatch):
    monkeypatch.setenv("HABARI_LEXICAL_THRESHOLD", "0.95")
    assert search("my account got hacked", "en", get_settings()).match is None


def test_invalid_numeric_settings_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("HABARI_LEXICAL_THRESHOLD", "banana")
    monkeypatch.setenv("HABARI_EMBED_THRESHOLD", "7")
    settings = get_settings()
    assert settings.lexical_threshold == 0.3
    assert settings.embed_threshold == 0.6


@pytest.mark.parametrize("url", ["not a url", "ftp://host", "http://host/path/x", "http://"])
def test_invalid_ollama_url_is_ignored(monkeypatch, url):
    monkeypatch.setenv("HABARI_OLLAMA_URL", url)
    assert get_settings().ollama_url is None


def test_valid_ollama_url_is_accepted_without_trailing_slash(monkeypatch):
    monkeypatch.setenv("HABARI_OLLAMA_URL", "http://127.0.0.1:11434/")
    assert get_settings().ollama_url == "http://127.0.0.1:11434"


def test_empty_message_tokens_do_not_crash():
    assert search("the and of", "en", KEYWORD_SETTINGS).match is None


def _fake_embedding(text, dimensions=96):
    vector = [0.0] * dimensions
    for token in retrieval.tokenize(text):
        bucket = int(hashlib.md5(token.encode()).hexdigest(), 16) % dimensions
        vector[bucket] += 1.0
    return vector


class FakeOllama:
    def __init__(self):
        self.calls = []

    def __call__(self, url, payload, timeout):
        self.calls.append((url, payload["model"], len(payload["input"])))
        return {"embeddings": [_fake_embedding(text) for text in payload["input"]]}


def test_embedding_backend_is_used_when_configured(monkeypatch):
    fake = FakeOllama()
    monkeypatch.setattr(retrieval, "_post_json", fake)
    settings = Settings(ollama_url="http://127.0.0.1:11434", embed_threshold=0.3)
    result = search("my account got hacked", "en", settings)
    assert result.backend == "embedding"
    assert result.match.entry.id == "hacked-account"
    assert fake.calls[0][0] == "http://127.0.0.1:11434/api/embed"
    assert fake.calls[0][1] == "nomic-embed-text"


def test_entry_embeddings_are_computed_once(monkeypatch):
    fake = FakeOllama()
    monkeypatch.setattr(retrieval, "_post_json", fake)
    settings = Settings(ollama_url="http://127.0.0.1:11434", embed_threshold=0.3)
    search("my account got hacked", "en", settings)
    search("how do I block a person", "en", settings)
    assert len(fake.calls) == 3  # one indexing call, then one query call per search


def test_embedding_threshold_gives_no_match_for_unrelated_text(monkeypatch):
    monkeypatch.setattr(retrieval, "_post_json", FakeOllama())
    settings = Settings(ollama_url="http://127.0.0.1:11434", embed_threshold=0.6)
    result = search("football scores today", "en", settings)
    assert result.backend == "embedding" and result.match is None


def test_embedding_failure_falls_back_to_keywords_and_backs_off(monkeypatch):
    calls = []

    def broken(url, payload, timeout):
        calls.append(1)
        raise OSError("connection refused")

    clock = {"now": 1000.0}
    monkeypatch.setattr(retrieval, "_post_json", broken)
    monkeypatch.setattr(retrieval.time, "monotonic", lambda: clock["now"])

    first = search("my account got hacked", "en", EMBED_SETTINGS)
    assert first.backend == "keyword" and first.match.entry.id == "hacked-account"
    assert len(calls) == 1

    clock["now"] += 30
    search("my account got hacked", "en", EMBED_SETTINGS)
    assert len(calls) == 1  # still backing off

    clock["now"] += retrieval.BACKOFF_SECONDS
    search("my account got hacked", "en", EMBED_SETTINGS)
    assert len(calls) == 2  # tried again after the pause


@pytest.mark.parametrize(
    "bad_response",
    [{"embeddings": []}, {"embeddings": [[0.0, 0.0]]}, {}, {"embeddings": "oops"}],
)
def test_malformed_embedding_responses_fall_back(monkeypatch, bad_response):
    monkeypatch.setattr(retrieval, "_post_json", lambda *args: bad_response)
    result = search("my account got hacked", "en", EMBED_SETTINGS)
    assert result.backend == "keyword"


def _raw(**overrides):
    entry = {"id": "a", "title": "t", "examples": ["x"], "answer": "ok"}
    entry.update(overrides)
    return {"meta": {"review_status": "draft"}, "entries": [entry]}


def test_parser_rejects_bad_entries():
    with pytest.raises(ValueError):
        parse_knowledge_base(_raw(answer="a" * (retrieval.MAX_ANSWER_LENGTH + 1)))
    with pytest.raises(ValueError):
        parse_knowledge_base(_raw(examples=[]))
    with pytest.raises(ValueError):
        parse_knowledge_base(_raw(title="  "))
    with pytest.raises(ValueError):
        parse_knowledge_base({"meta": {"review_status": "draft"}, "entries": []})
    duplicated = _raw()
    duplicated["entries"].append(dict(duplicated["entries"][0]))
    with pytest.raises(ValueError):
        parse_knowledge_base(duplicated)


def test_tokenizer_matches_inflected_forms():
    assert retrieval.tokenize("sharing shared shares") == ["shar", "shar", "shar"]
    assert retrieval.tokenize("bullied bullying") == ["bulli", "bulli"]
    assert math.isclose(sum(1 for _ in retrieval.tokenize("")), 0)
