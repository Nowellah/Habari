"""Simulated partners (Sauti 116, Police CFPU, UCC, school, counsellor).

A normal partner acknowledges at 10% of its window. The slow partner
(DEMO_SLOW_PARTNER, or a partner with slow_mode on) takes 300%, so the
escalation chain can be shown in a demo.
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from partners_mock.models import MockInbox

NORMAL_SHARE, SLOW_SHARE = 0.10, 3.0


def is_slow(partner):
    return partner.slow_mode or partner.slug == settings.DEMO_SLOW_PARTNER


def real_minutes(sla_minutes):
    return sla_minutes / max(settings.SLA_TIME_SCALE, 0.0001)


def deliver(referral, now=None):
    now = now or timezone.now()
    share = SLOW_SHARE if is_slow(referral.partner) else NORMAL_SHARE
    due = now + timedelta(minutes=real_minutes(referral.partner.ack_minutes * share))
    return MockInbox.objects.create(referral=referral, payload=referral.payload, received_at=now, ack_due_at=due)


def process_due(now=None):
    """Acknowledge every simulated referral whose time has come."""
    from core.router import acknowledge_referral

    now = now or timezone.now()
    for item in MockInbox.objects.filter(acked=False, ack_due_at__lte=now).select_related("referral"):
        acknowledge_referral(item.referral, now)
        item.acked = True
        item.save(update_fields=["acked"])
