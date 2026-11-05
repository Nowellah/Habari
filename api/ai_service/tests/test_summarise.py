from unittest import TestCase

from fastapi.testclient import TestClient

from ai_service.app import app
from ai_service.synthesis import extract_entities, summarise

client = TestClient(app)

MESSAGES = [
    {"text": "A man called @big_boss77 on Instagram keeps messaging me.", "at": "2026-11-05T10:00:00"},
    {"text": "He says he will post my nude pictures unless I send 50,000 shillings by Friday.",
     "at": "2026-11-05T10:02:00"},
    {"text": "His number is 0772 123 456 and he sent this link https://bad.example/x yesterday.",
     "at": "2026-11-05T10:05:00"},
]


class EntityTests(TestCase):
    def setUp(self):
        self.e = extract_entities(" ".join(m["text"] for m in MESSAGES))

    def test_handles(self):
        self.assertIn("@big_boss77", self.e["handles"])

    def test_phone_numbers_are_normalised(self):
        self.assertIn("+256772123456", self.e["phones"])

    def test_links(self):
        self.assertIn("https://bad.example/x", self.e["urls"])

    def test_amounts_in_ugx(self):
        self.assertIn(50000, self.e["amounts_ugx"])

    def test_dates_and_platforms(self):
        self.assertTrue({"friday", "yesterday"} <= set(self.e["dates"]))
        self.assertIn("instagram", self.e["platforms"])

    def test_no_entities_in_plain_text(self):
        e = extract_entities("they call me names at school")
        self.assertEqual(sum(len(v) for v in e.values()), 0)


class SummaryTests(TestCase):
    def setUp(self):
        self.out = summarise(MESSAGES)

    def test_summary_is_short(self):
        self.assertLessEqual(len(self.out["summary"].splitlines()), 5)

    def test_summary_keeps_the_most_serious_sentence(self):
        self.assertIn("nude pictures", self.out["summary"])

    def test_summary_never_invents_words(self):
        source = " ".join(m["text"] for m in MESSAGES)
        for line in self.out["summary"].splitlines():
            self.assertIn(line.lstrip("- ").strip(), source)

    def test_timeline_is_in_time_order(self):
        times = [t["at"] for t in self.out["timeline"]]
        self.assertEqual(times, sorted(times))
        self.assertEqual(len(times), 3)

    def test_empty_input(self):
        out = summarise([])
        self.assertEqual(out["summary"], "")
        self.assertEqual(out["timeline"], [])

    def test_endpoint_contract(self):
        r = client.post("/summarise", json={"messages": MESSAGES})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()), {"summary", "timeline", "entities", "method"})
