"""Core match and match-related statistics models."""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from core.models.season import Season
from core.models.team import Team

# Match model (Indonesian: Model pertandingan)
class Match(models.Model):
    match_id = models.CharField(max_length=100, unique=True, blank=True)
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

    def _generate_match_id(self):
        date_part = self.match_date.strftime("%Y%m%d%H%M")
        base = slugify(
            f"match-{self.season_id}-{date_part}-{self.home_team_id}-{self.away_team_id}"
        )[:100]
        candidate = base
        suffix = 2
        while type(self).objects.exclude(pk=self.pk).filter(match_id=candidate).exists():
            suffix_text = f"-{suffix}"
            candidate = f"{base[: 100 - len(suffix_text)]}{suffix_text}"
            suffix += 1
        return candidate
    
    # Mengoverride method save untuk validasi (Indonesian: Mengoverride method save untuk validasi)
    def save(self, *args, **kwargs):
        if not self.match_id and self.match_date and self.home_team_id and self.away_team_id:
            self.match_id = self._generate_match_id()
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
