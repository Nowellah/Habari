# Habari chat and triage service

A small FastAPI service that reads a child's message, assigns a severity (S1 to S4) and a category, and returns a reviewed reply plus the options and referral routes that may be offered. It stores nothing and has no database.

## Run it

Windows PowerShell, from this folder:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
$env:HABARI_HELPLINE_NUMBER = "<your real helpline number>"
uvicorn ai_service.engine.main:app --reload
```

Chat page: http://127.0.0.1:8000/ (a safety check screen, then the chat, with a quick exit button and a staff view toggle). Interactive API docs: http://127.0.0.1:8000/docs. Run the tests with `python -m pytest`.

## Endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /health` | Liveness check |
| `POST /api/ai/triage` | Classification only: severity, category, confidence, matched rule ids, flags |
| `POST /api/chat` | Classification plus reply, safe actions, path options, routing limits, and `guidance` for calm English chat messages |
| `POST /api/conversation/turn` | One step of the guided conversation. Body: `state` (returned by the previous turn, omit to start), then `text` or `choice`, plus `language`, `channel`, optional `category_hint`. Returns the next messages, choices, updated `state`, a staff `assessment`, and a `case_draft` once the child confirms |
| `POST /api/knowledge/search` | Look up the reviewed knowledge base. Body: `query`, optional `language`. Returns `matched`, `guidance`, `backend`, `best_score` |

Request body (both POST endpoints):

```json
{
  "message": "text, 1 to 2000 characters",
  "language": "en | lg",
  "channel": "chat | sms | ussd",
  "alleged_role": "stranger | online_contact | peer | family | teacher | guardian | unknown",
  "happening_now": true,
  "category_hint": "self_harm | immediate_danger | abuse | sextortion | grooming | harassment | account_scam | exposure | other"
}
```

Only `message` is required. Unknown fields are rejected.

## Severity rules

- S4: self-harm or immediate-danger phrases, or the child pressing a danger button (`category_hint` of `self_harm` or `immediate_danger`). Handled by `ai_service/engine/danger.py`, which uses only the standard library.
- Sextortion threats, or images plus a payment demand, are at least S3.
- A parent, teacher or guardian involved (from `alleged_role` or the text) together with any harm signal is at least S3 and `external_only`, which removes the `family_or_school` route.
- A message nothing recognises goes one level up (S2 when it has three or more words), asks a clarifying question and is flagged for human review. Messages that are not in English (`language` other than `en`) and match nothing become S3 with human review, because the keyword lists are English only.
- The child's selection and the text are combined and the higher severity wins. Nothing in the service lowers a severity.
- If triage itself fails, danger phrases still return S4 and everything else returns S3 with human review.

Danger phrases are matched even when negated ("I don't want to live" and "I don't want to die" both fire). This is intentional: a false alarm costs a review, a miss costs more.

## Reply content

Reply text lives in `ai_service/engine/content/en.json` and is currently marked `draft`. A language bundle in another language is used only when it is complete and its `meta.review_status` is `approved`. `ai_service/engine/content/lg.json` ships empty, so Luganda requests receive English with `language_fallback` and `needs_native_review` set to true. SMS and USSD replies are kept to 160 characters or fewer.

## Guided conversation

`ai_service/engine/conversation.py` runs the multi-turn flow: the child describes what happened, then is asked only what is still missing (is it happening now, who is involved), then offered options (talk to a person, make a report, keep proof, ask a question). Making a report shows exactly what would be passed on and asks for a yes before a `case_draft` is produced.

- **Stateless:** the server stores nothing. The browser keeps the `state` and sends it back each turn. It holds severity, category, flags, answers and the child's own words (at most 5 entries) so the child can review their report.
- **Severity only goes up:** every turn re-assesses all the child's words and merges the result, so a tampered or stale state cannot lower it.
- **The child rates it:** after describing what happened, every child is asked "How does this feel for you right now?" with five choices: a little, a lot, scared, in danger, or skip. The rating is a floor that can only raise severity: a lot gives at least S2, scared at least S3, in danger S4 with the safety check. A low rating never lowers what the system found, and the bot gently says so ("I know it may feel small...").
- **Danger first:** any text typed at any step is checked for danger before anything else and jumps to a safety check with the helpline.
- **SMS and USSD:** with `channel` set to `sms` or `ussd`, every message is split to 160 characters or fewer and each menu comes as numbered text (`menu_text`). A child can answer by typing a number.
- **Not saved:** `case_draft` is a payload for the case system. Nothing is stored here, and the final message only says the report is ready.

## Knowledge retrieval

`ai_service/engine/content/knowledge_en.json` holds about 30 short answers, each with several example phrasings, currently marked `draft`. Retrieval returns one approved answer or nothing. It never generates text.

- **Keyword backend (default):** TF-IDF over each entry's title and phrasings. A match needs a similarity of at least 0.3 and at least two shared content words.
- **Ollama embedding backend (optional):** used only when `HABARI_OLLAMA_URL` is set. It calls `/api/embed` with `HABARI_EMBED_MODEL` (default `nomic-embed-text`) and compares the question with every phrasing. Phrasing vectors are computed once and kept in memory. A match needs a cosine similarity of at least `HABARI_EMBED_THRESHOLD` (default 0.6).
- **Failure handling:** if Ollama errors, times out (`HABARI_OLLAMA_TIMEOUT`, default 3 seconds) or returns something malformed, the request uses the keyword backend and Ollama is not tried again for 60 seconds.
- **No match** means a person should handle the question. `guidance` is only attached to `/api/chat` for English chat messages at S1 or S2, never for danger, S3, SMS, USSD or Luganda.

To turn on Ollama embeddings (Windows PowerShell):

```
ollama pull nomic-embed-text
$env:HABARI_OLLAMA_URL = "http://127.0.0.1:11434"
uvicorn ai_service.engine.main:app --reload
```

The default embedding threshold of 0.6 is an untested guess. Call `/api/knowledge/search` with real questions and read `best_score` to choose a better value.

## Chat page

`ai_service/engine/static/` holds a plain HTML, CSS and JavaScript page served at `/`. It starts with "Are you safe right now?". The "No, I need help now" button sends the danger hint, so the reply is always S4. Quick exit (or pressing Escape twice) clears the page and leaves for a neutral site. The staff view shows severity, category, rules, routes and the raw response, and has demo controls for channel and language. The page runs the guided conversation, so the questions about whether it is happening now and who is involved are asked in the chat. In SMS and USSD mode replies show a character counter against the 160 limit.

The page loads no fonts, scripts or images from other sites, writes server text only with `textContent`, stores nothing in the browser, and is served with a strict content security policy and no-store caching. The options under each reply ("Make a report" and so on) are not connected to anything yet, and say so when pressed.

## Privacy

Nothing is stored. Logs contain only severity, category, channel and rule identifiers, never message text. Validation errors do not echo what was sent.

## Known limits

- All child-facing English text needs review by child protection staff before real use. Two statements need a product decision: "I won't share this with your family or school" and "a trained person may need to act to keep you safe, and they will tell you".
- The knowledge answers are drafts and need review by child protection staff. Retrieval quality has only been spot-checked on a small set of phrasings. No accuracy figure exists, and the Ollama backend has been tested only against a fake embedding service.
- The keyword lists are a first pass and have not been measured against a labelled test set. No accuracy figure exists yet.
- No Luganda text or Luganda keywords. Messages written in Luganda are not understood.
- The conversation flow strings are drafts like the other reply text, and Luganda has no flow text yet, so Luganda requests fall back to English.
- The helpline number is read from `HABARI_HELPLINE_NUMBER`. If it is unset, replies ask the child to find a trusted adult and `helpline_configured` is false.
- Route keys (`helpline`, `police`, `child_protection_partner`, and so on) are placeholders for the case system to map to real partners.
- SMS and USSD are only message shapes here. No gateway is connected.
