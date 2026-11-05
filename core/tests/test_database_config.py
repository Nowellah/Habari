from django.conf import settings
from django.test import SimpleTestCase


class SqliteConcurrencyConfigTests(SimpleTestCase):
    """The web app, the SLA watcher and background AI triage all write at once.
    Without these, SQLite answers 'database is locked' to a child mid-report."""

    def setUp(self):
        self.db = settings.DATABASES["default"]

    def test_writers_wait_instead_of_failing(self):
        self.assertGreaterEqual(self.db["OPTIONS"]["timeout"], 20)

    def test_transactions_take_the_write_lock_up_front(self):
        self.assertEqual(self.db["OPTIONS"]["transaction_mode"], "IMMEDIATE")

    def test_wal_mode_lets_readers_and_a_writer_work_together(self):
        self.assertIn("journal_mode=WAL", self.db["OPTIONS"]["init_command"])
