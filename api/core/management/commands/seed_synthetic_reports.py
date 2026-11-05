"""Clearly labelled SYNTHETIC reports so the heat map has something to show in a demo.

    python manage.py seed_synthetic_reports --count 120

Every case gets the flag "synthetic_demo". Remove them with --delete.
"""
import random

from django.core.management.base import BaseCommand

from core.geo import districts
from core.models import Case
from core.utils import new_case_code

WEIGHTS = {"Kampala": 30, "Wakiso": 18, "Mukono": 10, "Jinja": 8, "Gulu": 8, "Mbarara": 7, "Mbale": 5, "Lira": 4}


class Command(BaseCommand):
    help = "Create labelled synthetic reports for the heat map demo."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=120)
        parser.add_argument("--delete", action="store_true", help="Remove all synthetic demo reports.")

    def handle(self, *args, count=120, delete=False, **opts):
        demo = [c.pk for c in Case.objects.all() if "synthetic_demo" in (c.flags or [])]
        if delete:
            Case.objects.filter(pk__in=demo).delete()
            self.stdout.write(f"Removed {len(demo)} synthetic demo reports.")
            return
        rng = random.Random(7)
        names = [d for d, _, _ in districts()]
        weights = [WEIGHTS.get(n, 1) for n in names]
        for _ in range(count):
            Case.objects.create(code=new_case_code(), channel="web", pick=rng.choice("2345"),
                                severity=rng.choice([1, 2, 2, 3]), district=rng.choices(names, weights)[0],
                                flags=["synthetic_demo"], status=Case.Status.CLOSED,
                                close_reason="synthetic demo data")
        self.stdout.write(f"Created {count} synthetic demo reports (flag: synthetic_demo, status closed).")
