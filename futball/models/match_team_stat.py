"""Core match and match-related statistics models."""

from django.db import models
from django.core.exceptions import ValidationError
from futball.models.match import Match
from futball.models.team import Team

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