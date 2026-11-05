# HABARI — AI-Powered Child Online Safety Chatbot

**Intelligent Reporting, Response and Referral for Child Online Safety**  
*UCC Testbed Hackathon 2026*

---

## Quick Start (Windows PowerShell)

```powershell
cd C:\Users\UESR\Desktop\UI
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env    # then set your own STORAGE_SECRET in .env
python main.py
```

Open: **http://127.0.0.1:8080**

Demo mode is on by default (DEMO_MODE in .env) — no backend required. Never commit `.env`; it holds your secrets.

---

## Running Tests

```powershell
.\venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```

Expected: **65 passed, 0 failed**

---

## Environment Variables

Copy `.env.example` → `.env` and edit as needed.

| Variable         | Default                                  | Description                                      |
|------------------|------------------------------------------|--------------------------------------------------|
| `DJANGO_API_URL` | `http://127.0.0.1:8000`                  | Django REST API backend URL                      |
| `AI_SERVICE_URL` | `http://127.0.0.1:8001`                  | FastAPI AI service URL (future)                  |
| `STORAGE_SECRET` | `habari-dev-secret-change-in-production` | NiceGUI session storage secret — **change this** |
| `DEMO_MODE`      | `true`                                   | Enables demo mode (no live backend needed)       |

---

## Running with Django Backend

1. Start Django on port 8000.
2. Edit `.env`: set `DJANGO_API_URL=http://127.0.0.1:8000` and clear `DEMO_MODE`.
3. Run `python main.py`.

The API client (`services/api_client.py`) automatically detects the backend.  
If the backend is unreachable it falls back to demo mode transparently.

---

## Application Screens

| Route          | Screen              | Status        |
|----------------|---------------------|---------------|
| `/`            | Welcome             | ✅ Complete   |
| `/age`         | Age Selection       | ✅ Complete   |
| `/language`    | Language Selection  | ✅ Complete   |
| `/chat`        | Chatbot Interface   | ✅ Complete   |
| `/report`      | Report Review       | ✅ Complete   |
| `/confirmation`| Confirmation        | ✅ Complete   |
| `/status`      | Case Status         | ✅ Complete   |
| `/help`        | Human Help          | ✅ Complete   |

---

## Features

### Implemented and Tested
- Official Habari branding (deep teal, golden yellow, warm white)
- SVG logo (placeholder — replace with `assets/habari-logo.png` when available)
- All 8 screens with full navigation
- Full-height responsive chat interface — mobile and desktop
- Scrollable message history with child / bot bubbles
- Animated typing indicator
- Five reporting category quick-replies
- Multi-turn conversation state machine (10 states)
- Age-appropriate language for Under 10
- Keyword-based urgency detection (suicide, exploitation, physical danger, threats)
- Emergency guidance banner with Uganda Child Helpline **116**
- Report auto-built from conversation history
- Editable report description before submission
- Demo case code generation (format: `AB-7F3Q9X`)
- Case status screen with 7 status levels and color-coded badges
- Human help screen with clickable phone links (116, 999, 112)
- Quick Exit button on all screens (navigates to bbc.co.uk/cbbc)
- Session isolation — thread-safe in-memory store, no shared state
- XSS protection — all user input HTML-escaped before rendering
- DEMO MODE banner when env var is set
- Timezone-aware UTC timestamps (no deprecated `utcnow`)
- 65 automated tests — 0 failures

### Simulated in Demo Mode
- AI conversation replies (rule-based fallback)
- Report submission (generates a random case code)
- Case status lookup (returns a randomized demo status)

### Not Yet Connected (Backend Integration Points)
| Feature                        | Integration Point                            |
|-------------------------------|----------------------------------------------|
| Real report persistence        | `POST /api/channel/web`                      |
| AI language detection          | FastAPI `/language` endpoint                 |
| AI harm classification         | FastAPI `/triage` endpoint                   |
| AI severity scoring            | FastAPI `/triage` endpoint                   |
| AI-generated summaries         | FastAPI `/summarise` endpoint                |
| Live case status               | `GET /api/cases/{code}/status`               |
| Officer dashboard              | Separate Django admin interface              |
| Real Luganda/Swahili/Runyankore| Backend translation service                 |
| Voice/audio transcription      | FastAPI `/transcribe` endpoint               |

---

## Conversation Flow

```
Welcome → Age Selection → Language Selection → Chat
                                                 │
                              ┌──────────────────┤
                              │                  │
                         Pick Harm         Emergency Guidance
                              │                  │
                         Describe Problem   Human Help (/help)
                              │
                         Report Review (/report)
                              │
                         Confirmation (/confirmation)
                              │
                         Case Status (/status)
```

---

## Child Helpline Disclaimer

> The helpline number **116** shown is the Uganda Child Helpline.  
> **Verify this number is current and operational before deploying to production.**  
> Emergency numbers **999** and **112** should also be verified for the target country.

---

## Privacy and Security Notes

- No personal data is collected or required
- Conversation content is held in server memory only (cleared on restart)
- No sensitive data is placed in URLs or browser local storage
- Quick Exit navigates away but does not erase browser history
- Safeguarding records cannot be promised deleted — legal obligations may apply
- Change `STORAGE_SECRET` before any production deployment

---

## License

MIT License. Copyright © 2026 HABARI Project Contributors.
