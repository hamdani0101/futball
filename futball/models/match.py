"""Core match and match-related statistics models."""

from django.db import models
from django.core.exceptions import ValidationError
from futball.models.season import Season
from futball.models.team import Team

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.home_team} vs {self.away_team} ({self.match_date.date()})"
    
    # Mengoverride method save untuk validasi (Indonesian: Mengoverride method save untuk validasi)
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    # Validasi team harus home atau away team dalam match ini (Indonesian: Validasi team harus home atau away team dalam match ini)
    def clean(self):
        if self.home_team == self.away_team:
            raise ValidationError("Home and away team cannot be the same")
    
    # Ordering match by match_date (Indonesian: Pengurutan pertandingan berdasarkan tanggal pertandingan)
    class Meta:
        ordering = ["-match_date"]
        indexes = [
            models.Index(fields=["season"]),
            models.Index(fields=["home_team"]),
            models.Index(fields=["away_team"]),
            models.Index(fields=["status"]),
        ]