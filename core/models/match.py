"""Core match and match-related statistics models."""

from django.db import models
from core.models.season import Season
from core.models.team import Team
from core.models.stadium import Stadium

# Match model (Indonesian: Model pertandingan)
class Match(models.Model):
    match_id = models.CharField(max_length=100, unique=True)
    season = models.ForeignKey(Season, on_delete=models.CASCADE)
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="home_matches")
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="away_matches")
    match_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=[
            ("scheduled", "Scheduled"),
            ("finished", "Finished"),
            ("postponed", "Postponed"),
            ("cancelled", "Cancelled"),
            ("live", "Live"),
            ("paused", "Paused"),
        ],
        default="scheduled"
    )
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
    
    def __str__(self):
        return f"{self.home_team} vs {self.away_team} ({self.match_date.date()})"

    # Ordering match by match_date (Indonesian: Pengurutan pertandingan berdasarkan tanggal pertandingan)
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
                name="home_away_not_same",
            )
        ]
