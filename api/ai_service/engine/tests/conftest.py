import pytest
from fastapi.testclient import TestClient

from ai_service.engine.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def helpline(monkeypatch):
    monkeypatch.setenv("HABARI_HELPLINE_NUMBER", "0800 100 200")
    return "0800 100 200"


@pytest.fixture(autouse=True)
def no_helpline_by_default(monkeypatch):
    monkeypatch.delenv("HABARI_HELPLINE_NUMBER", raising=False)


@pytest.fixture(autouse=True)
def clean_retrieval_environment(monkeypatch):
    from ai_service.engine import retrieval

    for name in (
        "HABARI_OLLAMA_URL",
        "HABARI_EMBED_MODEL",
        "HABARI_EMBED_THRESHOLD",
        "HABARI_LEXICAL_THRESHOLD",
        "HABARI_OLLAMA_TIMEOUT",
    ):
        monkeypatch.delenv(name, raising=False)
    retrieval.reset_embedding_state()
    yield
    retrieval.reset_embedding_state()
