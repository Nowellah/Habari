# Third-party tools, models, data and services

Declare these in the pitch. **Check each licence and each platform's terms again before submission**; the notes below are our reading, not legal advice.

## Used in the running prototype

| Item | Used for | Licence or terms |
|---|---|---|
| Django | Web app | BSD-3-Clause |
| Django REST framework, django-htmx | Installed; not essential yet | BSD-3-Clause, MIT |
| requests | HTTP calls to Sunbird, SMS and messaging providers | Apache-2.0 |
| PyYAML, python-dotenv | Lexicon file, settings | MIT, BSD-3-Clause |
| pydantic | Rule engine result types | MIT |
| Leaflet | Heat map | BSD-2-Clause |
| OpenStreetMap tiles | Heat map background | Data ODbL; follow the OSM tile usage policy (use another tile server for heavy use) |
| Node.js test runner | Extension tests | MIT |

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
| Keycloak, PostgreSQL, Celery, Docker | Planned; the prototype uses Django groups, SQLite and simple loops |

## Data

All evaluation and demo data was written for this project and is synthetic. No real child data and no images of children are used anywhere. Luganda, Swahili and Runyankore text is draft and awaits native-speaker review.
