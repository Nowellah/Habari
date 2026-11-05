# Habari

A child-first online safety companion for Uganda (UCC Testbed Hackathon 2026, Track 5: intelligent reporting, response and referral).

A child can report something that happened online from almost any door: SMS, USSD, Telegram, WhatsApp, a web chat, a browser button, a voice note, or a share from a social app. Every door leads to the same case engine. Serious cases go to the right partner with a tracked acknowledgement, late cases escalate automatically, and the child can follow their case without giving a name.

## Repo layout

```
HABARI/
  api/    Django backend + AI service (Python 3.14, Django 5.2, FastAPI)
  web/    React frontend (Vite + TypeScript)
```

## Quick start

### Prerequisites

- Python 3.14
- Node 18+
- PostgreSQL 14+

### 1 — Backend (`api/`)

```powershell
cd api
py -3.14 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # fill in DB_PASSWORD and other secrets
python manage.py migrate
python manage.py seed_demo
```

Run services in separate terminals:

```powershell
# Terminal 1 — Django web app       http://localhost:8000
python manage.py runserver

# Terminal 2 — AI service           http://localhost:8001
python -m uvicorn ai_service.app:app --port 8001

# Terminal 3 — SLA watcher (demo speed: 1 min = 3 SLA hours)
$env:SLA_TIME_SCALE=180; python manage.py run_sla_watcher

# Terminal 4 — Telegram bot (optional, needs TELEGRAM_TOKEN in .env)
python manage.py run_telegram
```

### 2 — Frontend (`web/`)

```powershell
cd web
copy .env.example .env   # adjust API URLs if needed
npm install
npm run dev              # http://localhost:3000
```

## Environment variables

| File | Purpose |
|---|---|
| `api/.env` | Django secrets, DB credentials, third-party tokens |
| `web/.env` | Vite public API URLs (`VITE_` prefix only) |

Key `web/.env` variables:

```
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_AI_SERVICE_URL=http://127.0.0.1:8001
```

The Vite dev server proxies `/api/*` and `/static/*` to Django automatically, so relative paths like `fetch('/api/...')` work without hardcoding the base URL.

## Demo logins

Officers: `sarah`, `joseph`, `grace`, `moses`, `amina`, `peter`  
Supervisor: `esther`  
Password: `habari-demo` (set via `DEMO_OFFICER_PASSWORD` in `api/.env`)

## Key pages (Django)

| Page | URL |
|---|---|
| Child web chat | `/chat` |
| SMS simulator | `/sim/sms` |
| USSD simulator | `/sim/ussd` |
| Mock social app | `/mock/social` |
| Safety tips | `/kb` |
| Case status | `/status/<code>` |
| Officer dashboard | `/officer/` |
| Metrics / evaluation | `/metrics` |
| Feature status | `/about/status` |

## Tests

```powershell
# Backend
cd api; python manage.py test

# Frontend linting
cd web; npm run lint

# Browser extension
node --test api/extension/platform.test.js

# Evaluation (writes api/eval/results/metrics.json)
python api/eval/scripts/run_all.py
```

## Safety rules that never change

1. Nothing is sent to a parent or teacher without the child's choice, except immediate danger to life — decided by a named person — and the child is told.
2. The accused is never notified.
3. If the alleged person is an adult in charge (parent, guardian, teacher), only external routes are used; school and home are skipped.
4. AI can raise severity, never lower it. AI never closes a case or writes free text to a child.
5. If the AI is down, the child still gets a case code, the helpline number, and a human. Nothing waits for a model.
6. SMS and USSD replies contain a case code and plain words, never details.

## Privacy

- No real child data, ever. All test and demo data is synthetic and labelled.
- Children are known by an HMAC pseudonym. Phone numbers and Telegram IDs live only in a restricted vault; STOP erases the thread.
- Location is turned into a district; coordinates are never stored.
- Evidence (links, handles, screenshots) is hash-chained so tampering shows.

Third-party tools and licences: [`api/docs/third_party.md`](api/docs/third_party.md).
