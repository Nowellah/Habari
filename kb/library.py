"""Knowledge base: reviewed markdown articles in kb/articles, with simple search.

Articles are versioned in git. Search is word-based (TF-IDF); an embedding search
can replace it later without changing the pages.
"""
import html
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

FOLDER = Path(__file__).resolve().parent / "articles"
PUBLIC = {"child", "adult"}


@lru_cache
def articles():
    items = []
    for path in sorted(FOLDER.glob("*.md")):
        text = path.read_text(encoding="utf8")
        meta, body = {}, text
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        if m:
            for line in m.group(1).splitlines():
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()
            body = m.group(2)
        items.append({"slug": path.stem, "title": meta.get("title", path.stem), "audience": meta.get("audience", "child"),
                      "status": meta.get("status", ""), "body": body.strip()})
    return items


def _words(text):
    # Light plural folding so "teacher" finds "Teachers" and "pictures" finds "picture".
    return [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
            for w in re.findall(r"[a-z0-9]+", text.lower())]


def search(query, audiences=None):
    pool = [a for a in articles() if audiences is None or a["audience"] in audiences]
    terms = _words(query)
    if not terms:
        return pool
    docs = [Counter(_words(a["title"]) * 2 + _words(a["body"])) for a in pool]
    n = len(docs)
    scored = []
    for a, doc in zip(pool, docs):
        total = sum(doc.values()) or 1
        score = sum((doc[t] / total) * (math.log((1 + n) / (1 + sum(1 for d in docs if t in d))) + 1)
                    for t in terms if t in doc)
        if score > 0:
            scored.append((score, a))
    return [a for _, a in sorted(scored, key=lambda x: -x[0])]


def render_markdown(text):
    """Tiny, safe markdown: headings, bullet lists, paragraphs, bold. Everything is escaped first."""
    out, items, para = [], [], []

    def inline(s):
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(s))

    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
            items.clear()
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    for line in text.splitlines():
        s = line.strip()
        if not s:
            flush()
        elif s.startswith("# "):
            flush()
            out.append(f"<h2>{inline(s[2:])}</h2>")
        elif s.startswith("- "):
            if para:
                flush()
            items.append(s[2:])
        else:
            para.append(s)
    flush()
    return "\n".join(out)
