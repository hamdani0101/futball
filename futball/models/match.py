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

# Match team stats model (Indonesian: Model statistik tim pertandingan)
class MatchTeamStats(models.Model):
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="team_stats"
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    goals = models.IntegerField(default=0)
    xg = models.FloatField(default=0)
    shots = models.IntegerField(default=0)
    shots_on_target = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Validasi team harus home atau away team dalam match ini (Indonesian: Validasi tim harus home atau away team dalam match ini)
    def clean(self):
        if self.team not in [self.match.home_team, self.match.away_team]:
            raise ValidationError("Team must be home or away team in this match")

    # Mengoverride method save untuk validasi (Indonesian: Mengoverride method save untuk validasi)
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    # Unique together match dan team (Indonesian: Unik bersama match dan team)
    class Meta:
        unique_together = ("match", "team")
        
class MatchEvent(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=50)
    minute = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.match} - {self.team} - {self.event_type} - {self.minute}"
    
    # Validasi team harus home atau away team dalam match ini (Indonesian: Validasi tim harus home atau away team dalam match ini)
    def clean(self):
        if self.team not in [self.match.home_team, self.match.away_team]:
            raise ValidationError("Team must be home or away team in this match")
    
    # Mengoverride method save untuk validasi (Indonesian: Mengoverride method save untuk validasi)
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    # Unique together match dan team (Indonesian: Unik bersama match dan team)
    class Meta:
        unique_together = ("match", "team")