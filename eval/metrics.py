"""Plain-Python metrics, so the evaluation runs from a clean checkout with no extra installs."""
import math
from collections import Counter


def per_class(gold, pred, labels=None):
    labels = labels or sorted(set(gold) | set(pred))
    out = {}
    for c in labels:
        tp = sum(1 for g, p in zip(gold, pred) if g == c and p == c)
        fp = sum(1 for g, p in zip(gold, pred) if g != c and p == c)
        fn = sum(1 for g, p in zip(gold, pred) if g == c and p != c)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        out[c] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    return out


def macro_f1(report):
    supported = [v["f1"] for v in report.values() if v["support"]]
    return sum(supported) / len(supported) if supported else 0.0


def accuracy(gold, pred):
    return sum(g == p for g, p in zip(gold, pred)) / len(gold) if gold else 0.0


def confusion(gold, pred, labels):
    index = {c: i for i, c in enumerate(labels)}
    m = [[0] * len(labels) for _ in labels]
    for g, p in zip(gold, pred):
        if g in index and p in index:
            m[index[g]][index[p]] += 1
    return m


def wilson(successes, n, z=1.96):
    """95% confidence interval for a proportion. Honest about small test sets."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def binary_recall(gold_sev, pred_sev, threshold=3):
    """Recall and precision for 'high' (severity >= threshold). Missing a high case is the costly error."""
    pairs = list(zip(gold_sev, pred_sev))
    tp = sum(1 for g, p in pairs if g >= threshold and p >= threshold)
    fn = sum(1 for g, p in pairs if g >= threshold and p < threshold)
    fp = sum(1 for g, p in pairs if g < threshold and p >= threshold)
    recall = tp / (tp + fn) if tp + fn else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    return {"recall": recall, "precision": precision, "true_positives": tp, "false_negatives": fn,
            "false_positives": fp, "support": tp + fn, "ci95": wilson(tp, tp + fn)}


def counts(values):
    return dict(Counter(values))
