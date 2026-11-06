import pytest


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
