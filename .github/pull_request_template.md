## What changed

## How it was tested
- [ ] `python manage.py test` passes
- [ ] New behaviour has a test that failed before the change

## Safety checklist
- [ ] No real child data, names, phone numbers or images of children
- [ ] No secrets or tokens (they belong in `.env`, never in git)
- [ ] Child-facing words are plain and kind, with no case details in SMS or USSD
- [ ] `shared/feature_status.json` still labels everything honestly (Built / Simulated / Planned)
