from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core import calls
from core.models import Case
from core.tests.helpers import seed


class ChunkingTests(SimpleTestCase):
    def test_ten_second_chunks_with_two_second_overlap(self):
        self.assertEqual(calls.plan_chunks(30), [(0, 10), (8, 18), (16, 26), (24, 30)])

    def test_short_recording_is_one_chunk(self):
        self.assertEqual(calls.plan_chunks(6), [(0, 6)])

    def test_overlapping_words_are_not_repeated(self):
        merged = calls.merge_transcripts(["he says he will post", "will post my pictures unless", "unless I pay"])
        self.assertEqual(merged, "he says he will post my pictures unless I pay")

    def test_no_overlap_just_joins(self):
        self.assertEqual(calls.merge_transcripts(["hello there", "my name is"]), "hello there my name is")


class SimulatedCallTests(TestCase):
    def setUp(self):
        self.t0 = timezone.now()
        self.session = calls.start_call("sextortion_en", now=self.t0)

    def reveal(self, seconds):
        return calls.reveal_due(self.session, self.t0 + timedelta(seconds=seconds))

    def test_starting_a_call_opens_a_case(self):
        case = self.session.case
        self.assertEqual(case.channel, "voice")
        self.assertIn("simulated_call", case.flags)

    def test_transcript_arrives_bit_by_bit(self):
        self.assertEqual(self.reveal(0), [])
        first = self.reveal(15)
        self.assertTrue(first)
        later = self.reveal(60)
        self.assertTrue(later)
        self.assertFalse(set(s.pk for s in first) & set(s.pk for s in later))

    def test_each_segment_is_added_to_the_case_once(self):
        self.reveal(60)
        self.reveal(60)
        case = Case.objects.get(pk=self.session.case_id)
        self.assertEqual(case.messages.count(), self.session.segments.count())

    def test_danger_words_raise_the_case_while_the_call_goes_on(self):
        self.reveal(60)
        case = Case.objects.get(pk=self.session.case_id)
        self.assertEqual(case.severity, 4)
        self.assertIn("self_harm", case.flags)
        self.assertTrue(case.sla_events.filter(kind="severity_raised").exists())

    def test_flags_are_shown_per_segment(self):
        segments = self.reveal(60)
        self.assertTrue(any("sextortion" in s.flags for s in segments))


class CallPagesTests(TestCase):
    def setUp(self):
        seed()

    def test_officer_starts_a_call_and_follows_it(self):
        self.client.login(username="sarah", password="habari-demo")
        self.assertContains(self.client.get("/officer/calls"), "Simulated")
        r = self.client.post("/officer/calls/start", {"script": "sextortion_en"})
        self.assertEqual(r.status_code, 302)
        data = self.client.get(r["Location"].rstrip("/") + ".json").json()
        self.assertIn("segments", data)
        self.assertIn("case_code", data)

    def test_call_pages_need_login(self):
        self.assertEqual(self.client.get("/officer/calls").status_code, 302)
