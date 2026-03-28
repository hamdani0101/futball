"""Live match state model used during event replay and live views."""

from django.db import models

from core.models.match import Match


class MatchState(models.Model):
    """Track the latest scoreboard and flow metrics for a single match."""

    match = models.OneToOneField(
        Match,
        on_delete=models.CASCADE,
        related_name="state",
        primary_key=True,
    )
    current_minute = models.IntegerField(default=0)
    current_second = models.IntegerField(default=0)
    period = models.IntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=Match.Status.choices,
        default=Match.Status.SCHEDULED,
    )
    home_score = models.IntegerField(default=0)
    away_score = models.IntegerField(default=0)
    home_xg = models.FloatField(default=0.0)
    away_xg = models.FloatField(default=0.0)
    home_shots = models.IntegerField(default=0)
    away_shots = models.IntegerField(default=0)
    home_possession = models.IntegerField(default=0)
    away_possession = models.IntegerField(default=0)
    last_event = models.ForeignKey(
        "Event",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="match_states",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["last_event"]),
        ]

    def __str__(self):
        return f"State for match {self.match_id}"
