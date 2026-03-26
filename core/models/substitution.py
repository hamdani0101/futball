"""Substitution event model."""

from django.core.exceptions import ValidationError
from django.db import models

from core.models.event import Event
from core.models.match import Match
from core.models.player import Player
from core.models.team import Team


class Substitution(models.Model):
    """Store player change events as first-class match records."""

    event = models.OneToOneField(
        Event,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="substitution_detail",
    )
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="substitutions",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="substitutions",
    )
    player_out = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="substitutions_out",
    )
    player_in = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="substitutions_in",
    )
    minute = models.PositiveIntegerField(default=0)
    second = models.PositiveIntegerField(default=0)
    period = models.PositiveIntegerField(default=1)
    reason = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"{self.match_id} {self.team_id} "
            f"{self.player_out or '-'} -> {self.player_in or '-'}"
        )

    def clean(self):
        if self.team_id not in [self.match.home_team_id, self.match.away_team_id]:
            raise ValidationError("Substitution team must be home or away team in this match")

        if self.player_in_id and self.player_out_id and self.player_in_id == self.player_out_id:
            raise ValidationError("Substitution player_in and player_out must be different")

        if self.event_id:
            if self.event.match_id != self.match_id:
                raise ValidationError("Substitution event must belong to the same match")
            if self.event.type != Event.Type.SUBSTITUTION:
                raise ValidationError("Substitution event must have type substitution")

    class Meta:
        ordering = ["minute", "second", "id"]
        indexes = [
            models.Index(fields=["match"]),
            models.Index(fields=["team"]),
            models.Index(fields=["player_out"]),
            models.Index(fields=["player_in"]),
            models.Index(fields=["period"]),
            models.Index(fields=["minute", "second"]),
        ]
