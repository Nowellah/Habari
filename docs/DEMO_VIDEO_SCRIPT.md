# Habari: 3-minute demo video script

**Before recording:** run `python manage.py seed_demo`, start Django (port 8000) and the AI service (port 8001), and open two browser windows: the child chat (`/chat`, phone-sized) and the officer login (`/login/`, user `peter`). Mark one officer as on call. Close everything else on screen.

Total: 3:00. Times are guides, not exact.

---

### 0:00–0:20 · The problem
**Screen:** title slide "Habari: every report reaches help".
**Say:**
> "In UCC's own survey, 88% of children in Kampala had met harm online, and 74% never told anyone. Only 3 to 11 percent of serious cases ever reach the authorities. Children don't report because they're afraid of stigma, afraid of losing their phone, and there's no safe, simple way to do it. Habari is that way."

### 0:20–1:10 · A child reports sextortion
**Screen:** the child chat on a phone-sized window.
1. Tap **Talk to us**, then **Asked for pics/money**.
2. Type: *"a man I met on instagram says if I don't send him 100k on mobile money he will post my photos to my school group"*.

**Say while it replies:**
> "No name, no app, no login, and nothing stays on the phone. Within seconds Habari tells her to call 116, which is free. Then it tells her what to do right now: don't pay, keep screenshots, block him, and that she did nothing wrong. It asks if she's safe."

3. Tap **No, I am not safe**, then **Someone online**.
4. Point at the case code.
> "She gets a case code. That's all she needs to follow her case. She can do the same from SMS, USSD on any basic phone, Telegram or WhatsApp, in English, Luganda or Swahili."

### 1:10–1:50 · The officer side
**Screen:** officer dashboard, logged in as `peter`.
1. Point at the red **Alerts** box: *"DANGER: case HB-… (sextortion)"*.
2. Open the case.

**Say:**
> "The AI rated it severity 4, sextortion, from her words alone. It was assigned to an officer with cyber skills, and the reason is shown, so a supervisor can check or override it. The on-call officer is alerted. Because it's severity 4, it was already referred to the Sauti 116 helpline and the Police Child and Family Protection Unit."

3. Point at the referral list and the deadline clock.
> "Every severity-4 case must be acknowledged within 15 minutes. If not, Habari reminds, reassigns, pages the on-call officer and escalates to a second partner. No report is lost."

### 1:50–2:15 · The loop closes
**Screen:** back to the child chat. Type `STATUS` with the code.
> "When the helpline acknowledges, her status changes to 'A helper is working on your report'. Later Habari checks that she's safe."

### 2:15–2:40 · Honest about the AI
**Screen:** `/metrics`.
> "We measure ourselves. On a test set written before our latest rules, Habari catches 92% of serious cases, with two misses that we show. On harmless messages it raises 9 of 38: mostly Luganda and Swahili, which we send to a person on purpose rather than risk a miss. Next: a multilingual AI model on the Testbed GPU and Sunbird for local languages."

### 2:40–3:00 · Impact and close
**Screen:** closing slide.
> "Habari fits the services Uganda already has: Sauti 116, the Police and UCC. Children never pay. Funding comes from UCC and partners. Our next step is a two-district pilot with Sauti 116. Habari: every report reaches help."

---

## Live pitch: points to cover (judging weights in brackets)
- **The problem and the user** (relevance, 15%): the reporting silence; a child-first design.
- **Live demo** (technical, 20%): the same story as the video. Have a backup recording ready.
- **Testbed use** (10%): show the evidence of what ran on the Testbed (screenshots or logs).
- **Safety by design** (15%): no names, nothing on the device, districts not coordinates, quick exit, the adult-in-charge rule, rules can only raise severity.
- **Innovation** (10%): one case engine for every channel; local languages; tracked referral loop. Third-party tools and AI tools declared in `api/docs/third_party.md`.
- **Business case** (20%): see `docs/BUSINESS_CASE.md`.
- **Limits, said plainly** (pitch, 10%): simulated partners and channels, a small synthetic test set written by the team, drafts of local-language terms awaiting review.

## Likely judge questions
| Question | Answer in one line |
|---|---|
| Where is the AI? | Severity and category triage, language ID, speech to text; a zero-shot model slot ready for the GPU. Metrics at `/metrics`. |
| What if the AI is wrong? | It can only raise severity, a person reviews every serious case, and failures default to human review. |
| What if the AI service is down? | Rules still triage, the dashboard shows "Rules (AI down)", and unreadable text goes to a person. |
| How do you protect children's data? | Pseudonymous IDs, raw contact in a locked vault, hashed identifiers, district only, no cookies. |
| What happens when 10 serious cases come at once? | Each gets its own officer by skill, language and workload, partners are referred at once, and deadlines catch anything stuck. |
| How does it pay for itself? | Children free; UCC/Ministry funding, licences for NGOs and schools, donor pilots, operator zero-rating. |
