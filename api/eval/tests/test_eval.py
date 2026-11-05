import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from eval import metrics
from eval.scripts import make_synthetic, run_all


class MetricMathTests(SimpleTestCase):
    def test_precision_recall_f1_on_a_known_example(self):
        gold = ["a", "a", "b", "b"]
        pred = ["a", "b", "b", "b"]
        r = metrics.per_class(gold, pred)
        self.assertAlmostEqual(r["a"]["precision"], 1.0)
        self.assertAlmostEqual(r["a"]["recall"], 0.5)
        self.assertAlmostEqual(r["b"]["precision"], 2 / 3)
        self.assertAlmostEqual(r["b"]["recall"], 1.0)
        self.assertAlmostEqual(r["a"]["f1"], 2 * 1.0 * 0.5 / 1.5)

    def test_confusion_matrix_counts(self):
        cm = metrics.confusion(["a", "a", "b"], ["a", "b", "b"], labels=["a", "b"])
        self.assertEqual(cm, [[1, 1], [0, 1]])

    def test_class_never_predicted_has_zero_precision_not_a_crash(self):
        r = metrics.per_class(["a", "b"], ["b", "b"])
        self.assertEqual(r["a"]["precision"], 0.0)

    def test_high_severity_recall(self):
        r = metrics.binary_recall([4, 3, 2, 1, 3], [4, 2, 2, 3, 3], threshold=3)
        self.assertAlmostEqual(r["recall"], 2 / 3)
        self.assertAlmostEqual(r["precision"], 2 / 3)
        self.assertEqual(r["false_negatives"], 1)
        self.assertEqual(r["false_positives"], 1)

    def test_wilson_interval_contains_the_estimate(self):
        lo, hi = metrics.wilson(8, 10)
        self.assertLess(lo, 0.8)
        self.assertGreater(hi, 0.8)


class SyntheticDataTests(SimpleTestCase):
    def setUp(self):
        self.rows = make_synthetic.generate()

    def test_is_deterministic(self):
        self.assertEqual(self.rows, make_synthetic.generate())

    def test_has_enough_rows_and_languages(self):
        self.assertGreaterEqual(len(self.rows), 200)
        self.assertTrue({"en", "lg", "sw"} <= {r["language"] for r in self.rows})

    def test_split_is_by_template_so_test_never_sees_a_train_template(self):
        train = {r["template_id"] for r in self.rows if r["split"] == "train"}
        test = {r["template_id"] for r in self.rows if r["split"] == "test"}
        self.assertTrue(test)
        self.assertFalse(train & test)

    def test_every_category_is_in_the_test_split(self):
        cats = {r["category"] for r in self.rows}
        test_cats = {r["category"] for r in self.rows if r["split"] == "test"}
        self.assertEqual(cats, test_cats)

    def test_no_real_names_or_numbers(self):
        blob = json.dumps(self.rows)
        self.assertNotRegex(blob, r"\+2567\d{8}")


class RunAllTests(SimpleTestCase):
    def test_run_all_writes_metrics_with_required_sections(self):
        out = Path(tempfile.mkdtemp())
        path = run_all.main(out_dir=out)
        data = json.loads(path.read_text(encoding="utf8"))
        for key in ("synthetic_test", "hard_test", "hard_test_v2", "generated_at", "caveats"):
            self.assertIn(key, data)
        sev = data["synthetic_test"]["severity_high"]
        self.assertIn("recall", sev)
        self.assertIn("ci95", sev)
        self.assertIn("per_language", data["synthetic_test"])
        self.assertTrue((out / "errors.csv").exists())


class MetricsPageTests(SimpleTestCase):
    def test_page_shows_results(self):
        out = Path(tempfile.mkdtemp())
        run_all.main(out_dir=out)
        with override_settings(EVAL_RESULTS_DIR=out):
            r = self.client.get("/metrics")
        self.assertContains(r, "Recall on severity 3 and 4")
        self.assertContains(r, "Hard test set")

    def test_page_explains_how_to_run_when_there_are_no_results(self):
        with override_settings(EVAL_RESULTS_DIR=Path(tempfile.mkdtemp())):
            self.assertContains(self.client.get("/metrics"), "run_all.py")
