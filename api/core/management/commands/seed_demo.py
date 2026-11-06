"""Demo data: role groups, 5 simulated partners and 6 officers. Safe to run twice."""
import os

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

from core.models import Officer, Partner
from polls.models import Poll

GROUPS = ["officer", "supervisor", "safeguarding", "admin"]

PARTNERS = [
    # slug, display name, categories, districts, ack_minutes, phone
    ("sauti_116",   "Sauti 116 child helpline (simulated)",                    ["self_harm", "threats", "sextortion", "grooming", "exposure_by_authority", "cyberbullying"],                         [], 15,   "116"),
    ("police_cfpu", "Police Child and Family Protection Unit (simulated)",      ["self_harm", "threats", "sextortion", "grooming", "exposure_by_authority"],                                          ["Kampala", "Wakiso", "Mbarara", "Gulu"], 120, "0800 199 185"),
    ("ucc",         "Uganda Communications Commission (simulated)",             ["sextortion", "impersonation", "cyberbullying", "scam", "gambling_or_betting", "inappropriate_content"],             [], 1440, ""),
    ("school_focal","School safeguarding focal person (simulated)",             ["cyberbullying", "impersonation"],                                                                                    ["Kampala", "Wakiso"], 1440, ""),
    ("counsellor",  "Outside counsellor (simulated)",                          ["self_harm", "sextortion", "grooming", "exposure_by_authority", "cyberbullying", "inappropriate_content"],            [], 240,  ""),
]

# Officers paged for severity 4 cases, and supervisors who can reassign.
ON_CALL = {"peter"}
SUPERVISORS = ["esther"]

OFFICERS = [
    ("sarah", ["lg", "en"], ["child_protection"], "Kampala"),
    ("joseph", ["en", "sw"], ["cyber"], "Kampala"),
    ("grace", ["rn", "en"], ["counselling", "child_protection"], "Mbarara"),
    ("moses", ["lg", "en"], ["cyber", "child_protection"], "Wakiso"),
    ("amina", ["sw", "en"], ["counselling"], "Gulu"),
    ("peter", ["en"], ["child_protection"], "Kampala"),
]


class Command(BaseCommand):
    help = "Create demo groups, simulated partners and officers."

    def handle(self, *args, **opts):
        for name in GROUPS:
            Group.objects.get_or_create(name=name)
        officer_group = Group.objects.get(name="officer")

        for slug, name, cats, districts, ack, phone in PARTNERS:
            Partner.objects.update_or_create(
                slug=slug, defaults={"name": name, "categories": cats, "districts": districts,
                                     "ack_minutes": ack, "phone": phone}
            )

        password = os.getenv("DEMO_OFFICER_PASSWORD", "habari-demo")
        for username, langs, skills, district in OFFICERS:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(password)
                user.save()
            user.groups.add(officer_group)
            Officer.objects.update_or_create(
                user=user, defaults={"languages": langs, "skills": skills, "district": district,
                                     "on_call": username in ON_CALL}
            )

        Poll.objects.get_or_create(question="Did anyone make you uncomfortable online this week?",
                                   defaults={"options": ["Yes", "No", "Skip"]})

        supervisor_group = Group.objects.get(name="supervisor")
        for username in SUPERVISORS:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(password)
                user.save()
            user.groups.add(supervisor_group)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(PARTNERS)} partners, {len(OFFICERS)} officers and {len(SUPERVISORS)} supervisor. "
            f"Demo officer password: set by DEMO_OFFICER_PASSWORD (default for local demo only)."
        ))
