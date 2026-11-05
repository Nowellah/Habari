from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone

from channels.gateway import get_reporter
from core.models import Case
from core.utils import new_case_code


def seed():
    call_command("seed_demo", verbosity=0)


def make_case(severity=3, pick="2", channel="sms", sender="+256700000001", at=None, **kw):
    at = at or timezone.now()
    reporter = get_reporter(channel, sender, None) if sender else None
    return Case.objects.create(code=new_case_code(), reporter=reporter, channel=channel, pick=pick,
                               severity=severity, created_at=at, clock_started_at=at, **kw)


def after(t0, seconds):
    return t0 + timedelta(seconds=seconds)
