from django.db import models


class MockInbox(models.Model):
    """What a simulated partner received, and when it will acknowledge."""

    referral = models.ForeignKey("core.Referral", on_delete=models.CASCADE, related_name="mock_inbox")
    payload = models.JSONField()
    received_at = models.DateTimeField()
    ack_due_at = models.DateTimeField()
    acked = models.BooleanField(default=False)
