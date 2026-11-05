"""Retrieval over the reviewed knowledge base.

Only approved entry text is ever returned. Nothing is generated. Two backends
share one interface: a dependency-free keyword scorer, and Ollama embeddings
that are used only when HABARI_OLLAMA_URL is configured. A failing embedding
service falls back to keywords and is not retried for a minute.
"""
import json
import logging
import math
import re
import threading
import time
import urllib.request
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import Settings
from .danger import normalize

logger = logging.getLogger("habari.ai")

CONTENT_DIR = Path(__file__).parent / "content"
MAX_ANSWER_LENGTH = 400
BACKOFF_SECONDS = 60
MIN_SHARED_WORDS = 2
INDEX_TIMEOUT_FLOOR = 30.0

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are am as at be been but by can do does did for from had has have he her him his how i if in is it "
    "its me my of on or our she so that the their them they this to us was we were what when where which who why "
    "will with you your should would could about not no".split()
)


@dataclass(frozen=True)
class Entry:
    id: str
    title: str
    examples: tuple[str, ...]
    answer: str


@dataclass(frozen=True)
class KnowledgeBase:
    review_status: str
    entries: tuple[Entry, ...]


@dataclass(frozen=True)
class Match:
    entry: Entry
    score: float
    review_status: str


@dataclass(frozen=True)
class SearchResult:
    match: Match | None
    backend: str
    best_score: float


def parse_knowledge_base(raw: dict) -> KnowledgeBase:
    """Validate raw JSON content and build a knowledge base, or raise ValueError."""
    entries = []
    seen = set()
    for item in raw["entries"]:
        entry_id = item["id"]
        if entry_id in seen:
            raise ValueError(f"duplicate entry id {entry_id}")
        seen.add(entry_id)
        examples = tuple(item["examples"])
        answer = item["answer"].strip()
        if not item["title"].strip() or not examples or not answer:
            raise ValueError(f"entry {entry_id} has an empty field")
        if len(answer) > MAX_ANSWER_LENGTH:
            raise ValueError(f"entry {entry_id} answer is longer than {MAX_ANSWER_LENGTH} characters")
        entries.append(Entry(entry_id, item["title"].strip(), examples, answer))
    if not entries:
        raise ValueError("knowledge base has no entries")
    return KnowledgeBase(raw["meta"]["review_status"], tuple(entries))


@lru_cache(maxsize=None)
def load_knowledge_base(language: str) -> KnowledgeBase | None:
    path = CONTENT_DIR / f"knowledge_{language}.json"
    try:
        with open(path, encoding="utf-8") as handle:
            return parse_knowledge_base(json.load(handle))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.error("knowledge base for %s could not be loaded: %s", language, type(exc).__name__)
        return None


def _stem(token: str) -> str:
    for suffix in ("ing", "ed", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2 and not token.endswith("ss"):
            token = token[: -len(suffix)]
            break
    if token.endswith("e") and len(token) > 3:
        token = token[:-1]
    if token.endswith("y") and len(token) > 3:
        token = token[:-1] + "i"
    return token


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall(normalize(text)) if t not in _STOPWORDS and len(t) > 1]


def _entry_text(entry: Entry) -> str:
    return " ".join((entry.title, *entry.examples))


class _KeywordIndex:
    """TF-IDF vectors over each entry's title and example phrasings."""

    def __init__(self, kb: KnowledgeBase):
        documents = [Counter(tokenize(_entry_text(entry))) for entry in kb.entries]
        count = len(documents)
        frequency = Counter(token for doc in documents for token in doc)
        self._idf = {t: math.log((count + 1) / (df + 1)) + 1 for t, df in frequency.items()}
        self._vectors = [self._weigh(doc) for doc in documents]

    def _weigh(self, counts: Counter) -> dict[str, float]:
        weights = {t: c * self._idf[t] for t, c in counts.items() if t in self._idf}
        norm = math.sqrt(sum(w * w for w in weights.values()))
        return {t: w / norm for t, w in weights.items()} if norm else {}

    def scores(self, query: str) -> list[float]:
        """Cosine score per entry, zeroed when too few content words are shared with the query."""
        tokens = Counter(tokenize(query))
        vector = self._weigh(tokens)
        required = min(MIN_SHARED_WORDS, len(tokens))
        return [
            sum(w * doc.get(t, 0.0) for t, w in vector.items())
            if sum(1 for t in tokens if t in doc) >= required
            else 0.0
            for doc in self._vectors
        ]


@lru_cache(maxsize=None)
def _keyword_index(language: str) -> _KeywordIndex:
    return _KeywordIndex(load_knowledge_base(language))


def _best(kb: KnowledgeBase, scores: list[float], threshold: float, backend: str) -> SearchResult:
    best_index = max(range(len(scores)), key=scores.__getitem__)
    best_score = round(scores[best_index], 4)
    if best_score < threshold:
        return SearchResult(None, backend, best_score)
    return SearchResult(Match(kb.entries[best_index], best_score, kb.review_status), backend, best_score)


def _search_keywords(kb: KnowledgeBase, language: str, query: str, settings: Settings) -> SearchResult:
    return _best(kb, _keyword_index(language).scores(query), settings.lexical_threshold, "keyword")


# Embedding backend ---------------------------------------------------------

_state_lock = threading.Lock()
_state: dict = {"key": None, "vectors": None, "disabled_until": 0.0}


def reset_embedding_state() -> None:
    with _state_lock:
        _state.update(key=None, vectors=None, disabled_until=0.0)


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - address comes from configuration
        return json.loads(response.read().decode("utf-8"))


def _embed(settings: Settings, texts: list[str], timeout: float) -> list[list[float]]:
    body = _post_json(f"{settings.ollama_url}/api/embed", {"model": settings.embed_model, "input": texts}, timeout)
    vectors = body["embeddings"]
    if len(vectors) != len(texts):
        raise ValueError("embedding count does not match input count")
    unit_vectors = []
    for vector in vectors:
        norm = math.sqrt(sum(v * v for v in vector))
        if not norm:
            raise ValueError("embedding has zero length")
        unit_vectors.append([v / norm for v in vector])
    return unit_vectors


def _entry_vectors(kb: KnowledgeBase, language: str, settings: Settings) -> list[list[list[float]]]:
    """Embed every phrasing once per (service, model, language) and keep the result in memory."""
    key = (settings.ollama_url, settings.embed_model, language)
    with _state_lock:
        if _state["key"] == key:
            return _state["vectors"]
    phrases = [(i, text) for i, entry in enumerate(kb.entries) for text in (entry.title, *entry.examples)]
    embedded = _embed(settings, [text for _, text in phrases], max(settings.ollama_timeout, INDEX_TIMEOUT_FLOOR))
    grouped: list[list[list[float]]] = [[] for _ in kb.entries]
    for (index, _), vector in zip(phrases, embedded):
        grouped[index].append(vector)
    with _state_lock:
        _state.update(key=key, vectors=grouped)
    return grouped


def _search_embeddings(kb: KnowledgeBase, language: str, query: str, settings: Settings) -> SearchResult:
    grouped = _entry_vectors(kb, language, settings)
    query_vector = _embed(settings, [query], settings.ollama_timeout)[0]
    scores = [max(sum(a * b for a, b in zip(query_vector, v)) for v in vectors) for vectors in grouped]
    return _best(kb, scores, settings.embed_threshold, "embedding")


def search(query: str, language: str, settings: Settings) -> SearchResult:
    """Find the best approved entry, or report no match so a person handles the question."""
    kb = load_knowledge_base(language)
    if kb is None:
        return SearchResult(None, "none", 0.0)
    if settings.ollama_url and time.monotonic() >= _state["disabled_until"]:
        try:
            return _search_embeddings(kb, language, query, settings)
        except Exception as exc:  # noqa: BLE001 - any failure must fall back to keywords
            logger.warning("embedding backend unavailable, using keywords: %s", type(exc).__name__)
            with _state_lock:
                _state["disabled_until"] = time.monotonic() + BACKOFF_SECONDS
    return _search_keywords(kb, language, query, settings)
