"""Run the triage evaluation from a clean checkout.

    python eval/scripts/run_all.py

Writes eval/results/metrics.json and eval/results/errors.csv. The /metrics page
shows them. The triage is scored on the message text alone (no child pick), which
is harder than real use, where the child's own pick sets a floor.
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_service.language import detect_language  # noqa: E402
from ai_service.triage import CATEGORIES, triage  # noqa: E402
from eval import metrics  # noqa: E402
from eval.scripts import make_synthetic  # noqa: E402

RESULTS = ROOT / "eval" / "results"
HARD = ROOT / "eval" / "data" / "hard_test.csv"
HARD_V2 = ROOT / "eval" / "data" / "hard_test_v2.csv"

CAVEATS = [
    "All data is synthetic. No real child data was used.",
    "The same team wrote the keyword list and the synthetic messages, so synthetic scores are optimistic. "
    "The hand-written hard test set avoids the keywords and shows the real limits.",
    "Luganda and Swahili messages are drafts awaiting native-speaker review; per-language numbers are indicative only.",
    "Test sets are small; see the 95% confidence intervals.",
    "Scored on text only, without the child's own pick, which in real use sets a severity floor.",
    "Triage here is the lexicon rules plus the rule engine (ai_service/engine). The zero-shot model slot "
    "was not enabled for this run.",
    "Lexicon v0.2 rules were added from TRAINING-split errors only, with one exception: the 'kill yourself' "
    "rule was added after a test-set miss, for child safety. Baseline v0.1 results are kept in "
    "eval/results/metrics_baseline_v0.1.json.",
    "v0.3 rules were written from the misses in the first hard test set, so that set is NO LONGER BLIND and "
    "its score is optimistic. Before v0.3, the rules caught 9 of its 18 serious cases (0.50).",
    "The second hard test set (hard_test_v2) was committed before the v0.3 rules were written and was not "
    "used to choose them, so it is the fairest number here. Before v0.3 the rules caught 12 of its 26 "
    "serious cases (0.46). It was written by the same person as the v0.3 rules, so even this score may be "
    "optimistic. A test set written by someone outside the team is the next step.",
]


def score(rows):
    preds = [triage(r["text"]) for r in rows]
    gold_cat = [r["category"] for r in rows]
    pred_cat = [p["category"] for p in preds]
    gold_sev = [int(r["severity"]) for r in rows]
    pred_sev = [p["severity"] for p in preds]
    labels = CATEGORIES + ["unclear"]
    cat_report = metrics.per_class(gold_cat, pred_cat, labels)

    per_language = {}
    for lang in sorted({r["language"] for r in rows}):
        idx = [i for i, r in enumerate(rows) if r["language"] == lang]
        per_language[lang] = {
            "n": len(idx),
            "category_accuracy": metrics.accuracy([gold_cat[i] for i in idx], [pred_cat[i] for i in idx]),
            "severity_high": metrics.binary_recall([gold_sev[i] for i in idx], [pred_sev[i] for i in idx]),
            "language_id_accuracy": metrics.accuracy(
                [lang] * len(idx), [detect_language(rows[i]["text"])["language"] for i in idx]),
        }

    gold_role = [r["role"] == "authority" for r in rows]
    pred_role = [p["role"] == "authority" for p in preds]
    role_tp = sum(g and p for g, p in zip(gold_role, pred_role))
    role_support = sum(gold_role)

    errors = []
    for r, p in zip(rows, preds):
        missed_high = int(r["severity"]) >= 3 and p["severity"] < 3
        if missed_high or r["category"] != p["category"]:
            errors.append({"text": r["text"], "language": r["language"], "gold_category": r["category"],
                           "pred_category": p["category"], "gold_severity": r["severity"],
                           "pred_severity": p["severity"],
                           "error": "MISSED HIGH SEVERITY" if missed_high else "wrong category"})
    return {
        "n": len(rows),
        "category": {"macro_f1": metrics.macro_f1(cat_report), "accuracy": metrics.accuracy(gold_cat, pred_cat),
                     "per_class": {k: v for k, v in cat_report.items() if v["support"] or k in pred_cat}},
        "confusion": {"labels": labels, "matrix": metrics.confusion(gold_cat, pred_cat, labels)},
        "severity_high": metrics.binary_recall(gold_sev, pred_sev, 3),
        "severity_4": metrics.binary_recall(gold_sev, pred_sev, 4),
        "authority_role": {"recall": role_tp / role_support if role_support else 0.0, "support": role_support,
                           "ci95": metrics.wilson(role_tp, role_support)},
        "per_language": per_language,
    }, errors


def main(out_dir=RESULTS):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    synthetic = [r for r in make_synthetic.generate() if r["split"] == "test"]
    with HARD.open(encoding="utf8") as f:
        hard = list(csv.DictReader(f))
    with HARD_V2.open(encoding="utf8") as f:
        hard_v2 = list(csv.DictReader(f))
    syn_scores, syn_errors = score(synthetic)
    hard_scores, hard_errors = score(hard)
    hard_v2_scores, hard_v2_errors = score(hard_v2)
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": "lexicon rules v0.3 + rule engine (ai_service/triage.py), text only",
        "target": "Recall of at least 0.90 on severity 3 and 4",
        "synthetic_test": syn_scores,
        "hard_test": hard_scores,
        "hard_test_v2": hard_v2_scores,
        "caveats": CAVEATS,
    }
    path = out_dir / "metrics.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf8")
    with (out_dir / "errors.csv").open("w", newline="", encoding="utf8") as f:
        fields = ["set", "error", "language", "gold_category", "pred_category", "gold_severity", "pred_severity", "text"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for name, errs in (("synthetic_test", syn_errors), ("hard_test", hard_errors),
                           ("hard_test_v2", hard_v2_errors)):
            for e in errs:
                w.writerow({"set": name, **e})
    return path


if __name__ == "__main__":
    p = main()
    d = json.loads(p.read_text(encoding="utf8"))
    for name in ("synthetic_test", "hard_test", "hard_test_v2"):
        s = d[name]
        hi = s["severity_high"]
        print(f"{name}: n={s['n']}  severity 3-4 recall={hi['recall']:.2f} "
              f"(95% CI {hi['ci95'][0]:.2f}-{hi['ci95'][1]:.2f})  missed={hi['false_negatives']}  "
              f"category macro-F1={s['category']['macro_f1']:.2f}")
    print(f"wrote {p} and errors.csv")
