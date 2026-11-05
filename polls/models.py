from django.db import models


class Poll(models.Model):
    question = models.CharField(max_length=160)
    options = models.JSONField(default=list)  # e.g. ["Yes", "No", "Skip"]
    created_at = models.DateTimeField(auto_now_add=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.question


class PollResponse(models.Model):
    """One answer per child per poll. Only the district is kept, never the number."""

    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="responses")
    reporter = models.ForeignKey("core.Reporter", null=True, blank=True, on_delete=models.SET_NULL)
    answer = models.CharField(max_length=40)
    district = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["poll", "reporter"], name="one_answer_per_child")]
