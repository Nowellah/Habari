# Habari

A child-first online safety companion for Uganda (UCC Testbed Hackathon 2026, Track 5: intelligent reporting, response and referral).

A child can report something that happened online from almost any door: SMS, USSD, Telegram, WhatsApp, a web chat, a browser button, a voice note or a share from a social app. Every door leads to the same case engine. Serious cases go to the right partner with a tracked acknowledgement, late cases escalate by themselves, and the child can follow their case without giving a name.

**What works today:** see [`/about/status`](http://localhost:8000/about/status) (from `shared/feature_status.json`). Every feature is labelled **Built**, **Simulated** or **Planned**.

## Rules that never change

1. Nothing is sent to a parent or teacher without the child's choice, except immediate danger to life, decided by a named person, and the child is told.
2. The accused is never notified.
3. If the alleged person is an adult in charge (parent, guardian, teacher), only external routes are used; school and home are skipped.
4. AI can raise severity, never lower it. AI never closes a case or writes free text to a child.
5. If the AI is down, the child still gets a case code, the helpline and a human. Nothing waits for a model.
6. SMS and USSD replies contain a case code and plain words, never details.

## Quick start (Windows PowerShell)

```powershell
git clone https://github.com/Nowellah/Habari.git
cd Habari
py -3.14 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env            # then edit .env; never commit it
python manage.py migrate
python manage.py seed_demo        # roles, 5 simulated partners, 6 officers, 1 supervisor, a poll
```

Run in separate windows:

```powershell
python manage.py runserver                                   # 1 website            http://localhost:8000
python -m uvicorn ai_service.app:app --port 8001             # 2 AI service
$env:SLA_TIME_SCALE=180; python manage.py run_sla_watcher    # 3 SLA clock (demo speed: 1 min = 3 SLA hours)
python manage.py run_telegram                                # 4 Telegram bot (needs TELEGRAM_TOKEN)
```

Demo logins (local only): officers `sarah`, `joseph`, `grace`, `moses`, `amina`, `peter`; supervisor `esther`; password `habari-demo` (change with `DEMO_OFFICER_PASSWORD`).

## Where to look

| For | Page |
|---|---|
| Child web chat (speak, share location, quick exit) | `/chat` |
| SMS and USSD phone simulators | `/sim/sms`, `/sim/ussd` |
| Mock social app with a "Report to Habari" button | `/mock/social` |
| Safety tips and guides | `/kb` |
| Child's case status | `/status/<code>` |
| Officer queue, case pages, partner board, polls, map, calls | `/login/` then `/officer/` |
| Evaluation results and limits | `/metrics` |
| Feature status | `/about/status` |
| Browser extension | `extension/` (Chrome: `chrome://extensions`, Developer mode, Load unpacked) |

Send a message as any channel from PowerShell: `.\tools\send.ps1 sms HELP` (see the file for more).

## Tests and evaluation

```powershell
python manage.py test                 # about 350 tests
node --test extension/platform.test.js
python eval\scripts\run_all.py        # writes eval/results/metrics.json, shown at /metrics
```

Current evaluation (rules v0.3 plus the rule engine, text only): **hard test set 2 recall on severity 3-4 is 0.92 (24 of 26) against a 0.90 target**, but the same person wrote that set and the rules, and with 26 serious cases the 95% range is 0.76 to 0.98. Hard test set 1 was used to write the rules and is no longer blind. Keyword rules still miss new wording; the real AI model (zero-shot classifier, Sunbird) and a test set written outside the team are the next steps. Details and caveats on `/metrics`.

## Data and privacy

- No real child data, ever. All test and demo data is synthetic and labelled.
- Children are known by an HMAC pseudonym. Phone numbers and Telegram chat ids live only in a restricted vault; STOP erases the thread.
- Location is turned into a district; coordinates are never stored. Maps and poll results hide districts with fewer than 5 reports.
- Evidence (links, handles, screenshots) is hash-chained so tampering shows.
- Legal bases, retention periods, the adult-in-charge protocol and SLA times are proposals to be confirmed with counsel, a child-protection specialist and each partner.

## Layout

```
habari/          Django settings and URLs
core/            cases, triage rules, router, SLA, allocation, follow-up, linking, calls
channels/        gateway, SMS, USSD, Telegram, WhatsApp, voice, extension evidence
dashboard/       child pages, officer pages, metrics, installable app
polls/  kb/      U-Report style polls, knowledge base
partners_mock/   simulated partners
ai_service/      FastAPI: language, triage, translate, transcribe, summarise
eval/            synthetic data, hard test set, metrics
extension/       browser extension
shared/          harm picks, SLA rules, messages, districts, feature status
docs/            Siri guide, third-party list
```

Third-party tools and licences: [`docs/third_party.md`](docs/third_party.md).
