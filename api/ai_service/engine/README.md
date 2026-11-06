# Habari rules and knowledge engine

Plain Python modules used by the Django app (no separate service). They read a child's message, assign a severity (S1 to S4) and a category, and look up reviewed knowledge answers. Nothing is stored here.

## Modules

| Module | Purpose |
| --- | --- |
| `triage.py` | Combines the rules and returns a `TriageResult` (severity, category, confidence, rule ids, flags) |
| `danger.py` | Standard library only. Detects self-harm and immediate-danger phrases |
| `lexicon.py` | Keyword rules for harm categories |
| `bridge.py` | Adapter used by `core.ai_client` |
| `retrieval.py` | Finds one reviewed answer in `content/knowledge_en.json`, or nothing. It never generates text |
| `config.py` | Retrieval settings read from the environment |
| `schemas.py` | `Severity`, `Category`, `TriageResult` |

Run the tests from this folder with `python -m pytest`.

## Severity rules

- S4: self-harm or immediate-danger phrases, or a danger button press.
- Sextortion threats, or images plus a payment demand, are at least S3.
- A parent, teacher or guardian involved together with any harm signal is at least S3 and external only.
- A message nothing recognises goes one level up, is flagged for human review, and non-English text with no match becomes S3 with review, because the keyword lists are English only.
- Nothing lowers a severity. If triage fails, danger phrases still return S4 and everything else S3 with review.

Danger phrases are matched even when negated ("I don't want to live" and "I don't want to die" both fire). A false alarm costs a review; a miss costs more.

## Knowledge retrieval

`content/knowledge_en.json` holds about 30 short answers, each with several example phrasings, currently marked `draft`. The Django chat uses it for English web questions that are not reports.

- Keyword backend (default): TF-IDF over titles and phrasings. A match needs a similarity of at least 0.3 and at least two shared content words.
- Ollama embedding backend (optional): used only when `HABARI_OLLAMA_URL` is set, with `HABARI_EMBED_MODEL` (default `nomic-embed-text`) and `HABARI_EMBED_THRESHOLD` (default 0.6, an untested guess).
- If Ollama errors or times out (`HABARI_OLLAMA_TIMEOUT`, default 3 seconds), the keyword backend is used and Ollama is not tried again for 60 seconds.
- No match means the chat offers its normal menu.

## Privacy

Logs contain only severity, category, channel and rule identifiers, never message text.

## Known limits

- The knowledge answers are drafts and need review by child protection staff. Retrieval has only been spot-checked.
- The keyword lists are a first pass and have not been measured against a labelled test set.
- No Luganda keywords or knowledge answers.
- Three rule vocabularies still exist (`lexicon.yaml` in `core`, `lexicon.py`, `danger.py`) and have not been merged.
