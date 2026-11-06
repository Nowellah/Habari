# Third-party tools, models, data and services

Declare these in the pitch. **Check each licence and each platform's terms again before submission**; the notes below are our reading, not legal advice.

## Used in the running prototype

| Item | Used for | Licence or terms |
|---|---|---|
| Django | Web app | BSD-3-Clause |
| Django REST framework, django-htmx | Installed; not essential yet | BSD-3-Clause, MIT |
| requests, httpx | HTTP calls, tests | Apache-2.0, BSD-3-Clause |
| PyYAML, python-dotenv | Lexicon file, settings | MIT, BSD-3-Clause |
| FastAPI, uvicorn, python-multipart | AI service | MIT, BSD-3-Clause, Apache-2.0 |
| Leaflet | Heat map | BSD-2-Clause |
| OpenStreetMap tiles | Heat map background | Data ODbL; follow the OSM tile usage policy (use another tile server for heavy use) |
| Node.js test runner | Extension tests | MIT |
| PostgreSQL, psycopg | Database when DB_NAME is set (SQLite otherwise) | PostgreSQL Licence, LGPL-3.0 |
| React, React DOM, React Router | Web app pages (web/) | MIT |
| Vite, TypeScript, Vitest | Web app build and tests | MIT, Apache-2.0, MIT |
| ngrok | Public URL for SMS/USSD/WhatsApp callbacks during development | ngrok terms of service |

## Ready, used when credentials are set

| Item | Used for | Licence or terms |
|---|---|---|
| Telegram Bot API | Telegram channel | Telegram Bot API terms |
| Africa's Talking (SMS, USSD sandbox) | SMS and USSD | Africa's Talking terms; live shortcodes need operator and UCC approval |
| WhatsApp Cloud API (Meta) | WhatsApp channel | Meta Platform and WhatsApp Business terms |
| Sunbird AI API | Language ID, translation, speech to text | Sunbird API terms (check rate limits and commercial use) |
| Sunbird `asr-whisper-large-v3-salt` | Luganda and Runyankore speech to text | MIT (gated on Hugging Face) |
| faster-whisper / OpenAI Whisper | English and Swahili speech to text | MIT |
| Hugging Face Transformers + a zero-shot NLI model (mDeBERTa or BART-large-MNLI) | Optional triage classifier | Apache-2.0 library; check each model card's licence |

## Not used (noted from earlier plans)

| Item | Why not |
|---|---|
| NLLB-200 | CC-BY-NC (non-commercial), and no Runyankore |
| fastText lid.176 | No Luganda |
| Keycloak, Celery, Docker | Planned; the prototype uses Django groups and simple loops |

## AI tools used to build the prototype

The guide allows AI-assisted coding and writing tools if they are declared. These were used:

| Tool | Who | What it was used for |
|---|---|---|
| Claude Code (Anthropic, Claude Opus 5.5) | Eleanor Nabaloga | Reviewing teammates' branches; merging them and resolving conflicts; restoring the CI workflow; triage rules v0.3 and v0.4; writing hard_test_v2 and benign_test; officer alert, referral status and sextortion reply fixes; tests for these; submission documents (architecture, evaluation, business case, demo script). Every change was run against the test suite and reviewed before it was committed. |
| _Team members: add any other AI tools you used (for example ChatGPT, GitHub Copilot, Gemini) and what for, before code freeze._ | | |

AI tools did not supply any data about real children. The test messages they helped write are synthetic.

## Data

All evaluation and demo data was written for this project and is synthetic. No real child data and no images of children are used anywhere. Luganda, Swahili and Runyankore text is draft and awaits native-speaker review.
