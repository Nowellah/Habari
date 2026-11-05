# HABARI — AI-Powered Child Online Safety Chatbot

**Intelligent Reporting, Response and Referral for Child Online Safety**

HABARI is a Python-first, browser-based chatbot that helps children safely report online threats, abuse, harassment, and exploitation. It is built for the UCC Testbed Hackathon 2026 and is designed to be friendly, trustworthy, accessible, and demonstrable without a live backend.

---

## Setup (Windows PowerShell)

```powershell
cd C:\Users\UESR\Desktop\UI
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## Running in Demo Mode

Demo mode requires no backend. All AI and API calls fall back to built-in rule-based responses.

```powershell
# Ensure DEMO_MODE=true is set in .env (it is by default)
python main.py
```

Open your browser at: **http://127.0.0.1:8080**

---

## Running with Django Backend

1. Start the Django backend on port 8000 (or your preferred port).
2. Edit `.env`:
   ```
   DJANGO_API_URL=http://127.0.0.1:8000
   DEMO_MODE=
   ```
3. Run `python main.py`.

---

## Environment Variables

| Variable          | Default                                      | Description                                              |
|-------------------|----------------------------------------------|----------------------------------------------------------|
| `DJANGO_API_URL`  | `http://127.0.0.1:8000`                      | URL of the Django REST API backend                       |
| `AI_SERVICE_URL`  | `http://127.0.0.1:8001`                      | URL of the FastAPI AI service (future use)               |
| `STORAGE_SECRET`  | `habari-dev-secret-change-in-production`     | Secret key for NiceGUI session storage — **change this in production** |
| `DEMO_MODE`       | `true`                                       | Set to `true` to enable demo mode (no live backend needed) |

Copy `.env.example` to `.env` and fill in your values.

---

## Features

### Implemented
- Welcome screen with Start Chat, Get Help Now, and Quick Exit
- Age selection (Under 10 through 16–17 / Prefer not to say)
- Language selection (English, Luganda, Swahili, Runyankore)
- Full chat interface with scrollable history, quick replies, and loading indicator
- Keyword-based urgency detection (suicide, exploitation, physical danger, threats)
- Emergency guidance with helpline 116
- Demo mode rule-based conversation fallback
- Age-appropriate language (simplified replies for Under 10)
- Per-session isolation (thread-safe in-memory session store)
- Report review screen
- Report confirmation screen with case code display and copy
- Case status look-up screen
- Emergency help screen (116, police 999/112)
- XSS protection via `html.escape()` on all user input before rendering
- Quick Exit button on every screen (navigates to bbc.co.uk/cbbc)
- DEMO MODE banner when env var is set

### Simulated (Demo Mode)
- AI conversation responses (rule-based fallback when backend unreachable)
- Report submission (returns a generated case code)
- Case status retrieval (returns a demo status message)

### Not Yet Connected
- Live Django backend AI responses
- FastAPI AI service integration
- Persistent case database
- Safeguarding officer dashboard
- Real-time notifications to officers
- Full Luganda / Swahili / Runyankore translations

---

## Running Tests

```powershell
cd C:\Users\UESR\Desktop\UI
python -m pytest tests/ -v
```

---

## Child Helpline Disclaimer

> The helpline number **116** shown in this application is the Uganda Child Helpline.
> Please verify this number is current and correct before deploying to production.

---

## License

MIT License. Copyright (c) 2026 HABARI Project Contributors.
