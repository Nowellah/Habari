# Habari evaluation: triage accuracy, false negatives and false positives

**What is measured:** whether the triage gives a child's message the right severity (1 to 4) and category, from the text alone. Severity 3 and 4 mean a person must act within 2 hours or 15 minutes.

**Method:** lexicon rules v0.4 plus the rule engine (`api/ai_service/`), text only, with no help from the child's own button choice (which in real use sets a minimum severity). Run it yourself with `python eval/scripts/run_all.py` in `api/`; results also show at `/metrics`. Every miss and false alarm is listed in `api/eval/results/errors.csv`.

**Target:** catch at least 90% of severity 3 and 4 messages.

## Results

| Test set | Messages | Serious caught (severity 3–4) | False negatives (serious missed) | False positives (raised to 3–4 wrongly) |
|---|---|---|---|---|
| **Hard test set 2** (fairest, see below) | 36 | **24 of 26 = 0.92** (95% CI 0.76–0.98) | **2** | **0** of 10 non-serious |
| **Harmless messages** (benign_test) | 38 | – | – | **9 of 38 = 0.24** (95% CI 0.13–0.39) |
| Hard test set 1 (used to write the rules) | 23 | 18 of 18 = 1.00 | 0 | 0 |
| Synthetic test set (optimistic) | 90 | 54 of 54 = 1.00 | 0 | 16 of 36 non-serious |

### False negatives (serious messages missed), hard test set 2
1. "he sent me a photo of my house and said see you soon": a veiled threat with no threatening words. Rated 2.
2. "a 30 year old keeps telling me i look older than my age and asks me to video call at night": grooming by flattery. Rated 2.

Both still reach a person (severity 2, a 24-hour deadline). Neither was ignored.

**Severity 4 specifically:** 11 of 15 severity-4 messages were rated 4. The other 4 were rated 3, so they still reach a person within 2 hours, but not within the 15 minutes severity 4 needs.

### False positives (harmless messages raised), benign_test
- **English: 2 of 30.** "my friend is waiting for me at the shop" (a "waiting for me" danger rule) and "my mum wants me to send her photos from the school trip" (any request for photos is treated as grooming).
- **Luganda and Swahili: 7 of 8.** This is deliberate. Text the rules cannot read is sent to a person at severity 3 rather than being treated as safe. Real AI models for Luganda and Swahili (Sunbird) would lower this.

A false alarm costs an officer a few minutes. A miss can cost a child's safety. The rules are set to prefer false alarms, and the numbers above show that trade-off.

### Other measures (hard test set 2)
- Category correct (macro F1): 0.65. The severity is usually right even when the category label is not.
- Adult in charge (parent, teacher, pastor) correctly detected: 4 of 4, so those cases are kept away from the family and school.
- Language identified: English 32/32, Swahili 2/2, Luganda 1/2.

## How fair are these numbers?

- **Hard test set 2** was committed (`f245f68`) **before** the v0.3 rules were written, and scored 0.46 before them. The v0.4 trusted-adult change was then checked against it, and its warning-sign list was chosen after looking at 2 misses, so it is **no longer fully blind**. Its blind score, before v0.4, was also 0.92.
- **Hard test set 2 and the rules were written by the same person**, with an AI coding assistant (declared in `api/docs/third_party.md`), so even 0.92 may be optimistic.
- **Hard test set 1** was used to write the v0.3 rules. Its 1.00 is not a fair score; before v0.3 it was 0.50.
- **benign_test** was committed before it was scored, and no rule was changed after scoring it.
- **The sets are small** (26 serious messages in set 2), hence the wide confidence intervals.
- **All data is synthetic.** No real child data or images were used. Luganda and Swahili lines are drafts awaiting native-speaker review.

## Progress

| Version | Hard test set 2 | Hard test set 1 |
|---|---|---|
| Lexicon v0.2 (start of Day 1) | – | 0.22 |
| v0.2 + rule engine | 0.46 | 0.50 |
| v0.3 rules | 0.92 | 1.00* |
| v0.4 (fewer trusted-adult false alarms) | 0.92* | 1.00* |

\* no longer blind for that set.

## Next steps
1. A test set written by someone **outside the team** (a child-protection practitioner) for a fully blind score.
2. Turn on the **zero-shot classifier** slot (a multilingual NLI model on the Testbed GPU) to catch wording that rules miss, like the two misses above.
3. **Sunbird** language ID and translation, so Luganda and Swahili messages are read rather than sent straight to a person.
4. Native-speaker review of every Luganda, Swahili and Runyankore term.
