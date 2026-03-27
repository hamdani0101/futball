"""Core event statistics models."""

from django.db import models

from core.models.team import Team
from core.models.match import Match
from core.models.player import Player

# Event model
class Event(models.Model):
    class Type(models.TextChoices):
        SHOT = "shot", "Shot"
        PASS = "pass", "Pass"
        FOUL = "foul", "Foul"
        CARD = "card", "Card"
        SUBSTITUTION = "substitution", "Substitution"
        DUEL = "duel", "Duel"
        RECOVERY = "recovery", "Recovery"
        CLEARANCE = "clearance", "Clearance"

    external_event_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
    )
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="events")
    period = models.PositiveIntegerField(default=1)
    minute = models.PositiveIntegerField(default=0)
    second = models.PositiveIntegerField(default=0)
    event_index = models.PositiveIntegerField(default=0)
    possession = models.PositiveIntegerField(default=0)
    timestamp_ms = models.IntegerField(null=True, blank=True)
    x = models.FloatField(null=True, blank=True)
    y = models.FloatField(null=True, blank=True)
    type = models.CharField(max_length=20, choices=Type.choices)
    play_pattern = models.CharField(max_length=50, blank=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="events")
    player = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    extra_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.match_id} {self.type} {self.minute}:{self.second:02d}"

    class Meta:
        ordering = ["match", "period", "minute", "second", "event_index", "id"]
        indexes = [
            models.Index(fields=["match"]),
            models.Index(fields=["match", "event_index"]),
            models.Index(fields=["minute", "second"]),
            models.Index(fields=["period"]),
            models.Index(fields=["type"]),
            models.Index(fields=["team"]),
            models.Index(fields=["player"]),
            models.Index(fields=["possession"]),
            models.Index(fields=["extra_data"]),
        ]
