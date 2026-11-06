# Changelog

Each phase is tagged in git. Feature status lives in `shared/feature_status.json` (shown at `/about/status`).

## Unreleased – Luganda replies (6 Nov 2026)
Children who write or choose Luganda are answered in Luganda: every reply, button, status update, check-in and SLA reminder (shared/messages_lg.json, draft wording for native review). Missing texts fall back to English. More Luganda words for language detection, and Luganda threat words so a Luganda sextortion report gets severity 4 like English. Harmless-message false alarms 9 -> 10 of 38 ("ndi bulungi" is now recognised as Luganda and sent to a person).

## demo flow fixes (5 Nov 2026)
Sextortion reports get severity 4 and the helpline in the first reply (the rule engine now runs in the first pass), plus what to do right now: don't pay, keep proof, block. Officer alerts now show on the dashboard (they needed email addresses or phone-number usernames before, and no email backend was set). Sending referrals marks the case Referred and a partner acknowledgement marks it Acknowledged, so the child's status words move on.

## triage rules v0.4 (5 Nov 2026)
Naming a parent, teacher or other adult in charge is no longer severity 3 by itself ("my teacher says I did well"). It needs a sign of harm (hitting, touching, threats, grooming) or a warning sign (alone with them, at night, a locked door, messages about the child's body, repeated private messages). Only then is the case routed with the adult-in-charge rule. New harm_by_person flag; lg, sw and rn terms are drafts.

## triage rules v0.3 (5 Nov 2026)
Broader rules for indirect self-harm, overdose, strangers near the child, sextortion with a payment demand (now severity 4), requests for images (now severity 3), doctored images, trusted adults (coach, pastor, step-parents) and unrecognised languages (now severity 3 for review). Second hard test set added before the rule changes.
Evaluation: severity 3-4 recall 0.46 → 0.92 on hard test set 2 (written by the same person as the rules, so optimistic). Hard test set 1 was used to write the rules and is no longer blind (0.50 → 1.00).

## v0.5.0 – Phase 4b (5 Nov 2026)
Duplicate and repeat-offender finder, knowledge base, WhatsApp adapter (simulated), simulated call with live transcript, Siri shortcut guide, README, feature status page, third-party list.

## v0.4.0 – Phase 4 (5 Nov 2026)
Browser extension with evidence and screenshots, voice notes with confirmation, evaluation and `/metrics`, U-Report style polls, location to district and heat map, case summaries, installable app with share target.
Evaluation: hard test set recall on severity 3-4 is 0.22 against a 0.90 target.

## v0.3.0 – Phase 3 (5 Nov 2026)
Referral router with the adult-in-charge rule, simulated partners, SLA clock and escalation, officer allocation, follow-up loop and safety check-in, officer case pages and partner board. SQLite set up for several writers.

## v0.2.0 – Phase 2 (5 Nov 2026)
AI service (language, triage, translation slot), background AI triage with a safe fallback, language question, Telegram bot, SMS and USSD with simulators, web chat.

## v0.1.0 – Phase 1 (5 Nov 2026)
Case engine, channel gateway, harm picks and severity, keyword rules, private reporter IDs, STATUS/STOP/PIN, evidence hash chain, status page and officer queue. Project renamed from Mukwano to Habari.
