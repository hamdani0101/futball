"""Core match and match-related statistics models."""

from django.db import models
from core.models.season import Season
from core.models.team import Team
from core.models.stadium import Stadium

# Match model (Indonesian: Model pertandingan)
class Match(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        FINISHED = "finished", "Finished"
        POSTPONED = "postponed", "Postponed"
        CANCELLED = "cancelled", "Cancelled"
        LIVE = "live", "Live"
        PAUSED = "paused", "Paused"
        
    season = models.ForeignKey(Season, on_delete=models.CASCADE)
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="home_matches")
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="away_matches")
    stage = models.CharField(max_length=100, null=True, blank=True)
    match_date = models.DateTimeField()
    match_week = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    stadium = models.ForeignKey(
        Stadium,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matches"
    )
    external_id = models.IntegerField(
        null=True,
        blank=True,
        unique=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Unique constraint to ensure home and away teams are different
    class Meta:
        ordering = ["-match_date"]
        indexes = [
            models.Index(fields=["season"]),
            models.Index(fields=["match_date"]),
            models.Index(fields=["season", "match_date"]),
            models.Index(fields=["home_team"]),
            models.Index(fields=["away_team"]),
            models.Index(fields=["status"]),
            models.Index(fields=["stadium"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(home_team=models.F("away_team")),
                name="home_team_not_equal_away_team"
            ),
        ]

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} ({self.match_date.date()})"