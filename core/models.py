import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

CHANNELS = [(c, c) for c in ("sms", "ussd", "telegram", "whatsapp", "web", "extension", "voice", "siri")]


def _new_key():
    return secrets.token_hex(24)


class Reporter(models.Model):
    """A child, known only by a pseudonymous ID. No name, no number here."""

    pseudo_id = models.CharField(max_length=20, unique=True)
    channel = models.CharField(max_length=12, choices=CHANNELS)
    language = models.CharField(max_length=8, blank=True)
    pin_hash = models.CharField(max_length=64, blank=True)
    basic_phone = models.BooleanField(default=False)
    opted_out = models.BooleanField(default=False)
    poll_opt_in = models.BooleanField(default=False)
    # Coarse location only: a district name, never coordinates.
    district = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.pseudo_id


class ReporterVault(models.Model):
    """Raw contact, visible only to the safeguarding group."""

    reporter = models.OneToOneField(Reporter, on_delete=models.CASCADE, related_name="vault")
    raw_contact = models.CharField(max_length=64)


class Conversation(models.Model):
    reporter = models.ForeignKey(Reporter, on_delete=models.CASCADE, related_name="conversations")
    channel = models.CharField(max_length=12, choices=CHANNELS)
    state = models.CharField(max_length=20, default="START")
    draft = models.JSONField(default=dict, blank=True)
    case = models.ForeignKey("Case", null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)


class Case(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        TRIAGED = "triaged", "Triaged"
        ASSIGNED = "assigned", "Assigned"
        REFERRED = "referred", "Referred"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"
        SAFETY_CHECK = "safety_check", "Safety check-in"
        CLOSED = "closed", "Closed"
        CLOSED_UNFOUNDED = "closed_unfounded", "Closed: unfounded"
        CLOSED_CHILD_STOP = "closed_child_stop", "Closed: child asked to stop"

    code = models.CharField(max_length=9, unique=True)
    reporter = models.ForeignKey(Reporter, null=True, blank=True, on_delete=models.SET_NULL, related_name="cases")
    channel = models.CharField(max_length=12, choices=CHANNELS)
    pick = models.CharField(max_length=2, blank=True)
    category = models.CharField(max_length=40, blank=True)
    severity = models.PositiveSmallIntegerField(default=1)
    alleged_role = models.CharField(max_length=20, blank=True)
    language = models.CharField(max_length=8, blank=True)
    language_conf = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    district = models.CharField(max_length=60, blank=True)
    is_late = models.BooleanField(default=False)
    summary = models.TextField(blank=True)
    flags = models.JSONField(default=list, blank=True)
    assigned_officer = models.ForeignKey("Officer", null=True, blank=True, on_delete=models.SET_NULL)
    # How the current severity was decided: "rules", "ai" or "rules_ai_down".
    triage_source = models.CharField(max_length=20, default="rules")
    triaged_at = models.DateTimeField(null=True, blank=True)
    assignment_reason = models.CharField(max_length=300, blank=True)
    routing_note = models.CharField(max_length=300, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    checkin_due_at = models.DateTimeField(null=True, blank=True)
    checkin_count = models.PositiveSmallIntegerField(default=0)
    rating = models.CharField(max_length=10, blank=True)
    # Details pulled from the child's messages: handles, phones, links, amounts, dates, platforms.
    entities = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    # SLA clock. ack_at and first_response_at belong to the current clock;
    # a reset clears them and the earlier times stay in SLAEvent.
    clock_started_at = models.DateTimeField(default=timezone.now)
    clock_cycle = models.PositiveIntegerField(default=0)
    ack_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-severity", "created_at"]

    def __str__(self):
        return self.code


class Message(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="messages")
    direction = models.CharField(max_length=3, choices=[("in", "in"), ("out", "out")])
    text = models.TextField()
    text_en = models.TextField(blank=True)
    channel = models.CharField(max_length=12, choices=CHANNELS)
    created_at = models.DateTimeField(auto_now_add=True)


class Evidence(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="evidence")
    kind = models.CharField(max_length=20)
    value = models.TextField()
    value_sha256 = models.CharField(max_length=64)
    prev_hash = models.CharField(max_length=64)
    chain_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class Officer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    languages = models.JSONField(default=list)
    skills = models.JSONField(default=list)
    district = models.CharField(max_length=60, blank=True)
    load = models.PositiveIntegerField(default=0)
    on_call = models.BooleanField(default=False)
    conflict_flag = models.BooleanField(default=False)

    def __str__(self):
        return self.user.get_username()


class Partner(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    categories = models.JSONField(default=list)
    districts = models.JSONField(default=list)
    ack_minutes = models.PositiveIntegerField(default=120)
    slow_mode = models.BooleanField(default=False)
    # Key the partner sends in X-Partner-Key when acknowledging a referral.
    api_key = models.CharField(max_length=64, default=_new_key)

    def __str__(self):
        return self.name


class Referral(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="referrals")
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT)
    payload = models.JSONField(default=dict)
    sent_at = models.DateTimeField(default=timezone.now)
    ack_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default="sent")


class OutboundSMS(models.Model):
    """Every SMS we send. Holds no phone number: the number comes from the vault
    (or the incoming request) at send time. The SMS simulator shows these."""

    reporter = models.ForeignKey(Reporter, null=True, on_delete=models.SET_NULL, related_name="outbound_sms")
    text = models.TextField()
    provider = models.CharField(max_length=20, default="simulator")
    provider_status = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    """A message for staff: the assigned officer, supervisors, the on-call responder or a partner."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="notifications")
    audience = models.CharField(max_length=20)  # officer, supervisor, on_call, partner
    officer = models.ForeignKey(Officer, null=True, blank=True, on_delete=models.SET_NULL)
    text = models.CharField(max_length=300)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]


class SLAEvent(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="sla_events")
    kind = models.CharField(max_length=30)
    clock_cycle = models.PositiveIntegerField(default=0)
    detail = models.TextField(blank=True)
    at = models.DateTimeField(default=timezone.now)
