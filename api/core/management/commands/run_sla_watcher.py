"""Runs the SLA clock, the simulated partners and the safety check-ins.

    python manage.py run_sla_watcher            # every 5 seconds until Ctrl+C
    python manage.py run_sla_watcher --once     # one pass (for tests and cron)
"""
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from core import sla


class Command(BaseCommand):
    help = "Check SLA clocks, escalate late cases, run simulated partners and safety check-ins."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run one pass and stop.")
        parser.add_argument("--interval", type=float, default=5.0, help="Seconds between passes.")

    def handle(self, *args, once=False, interval=5.0, **opts):
        if once:
            sla.tick()
            return
        self.stdout.write(self.style.SUCCESS(
            f"SLA watcher running every {interval:g} s (time scale x{settings.SLA_TIME_SCALE:g}). Ctrl+C to stop."))
        try:
            while True:
                sla.tick()
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write("Stopped.")
