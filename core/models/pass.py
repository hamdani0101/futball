"""Pass event model for passing analytics."""

from django.core.exceptions import ValidationError
from django.db import models

from core.models.match import Match
from core.models.player import Player
from core.models.team import Team

class Pass(models.Model):
    """Store a pass event with spatial and contextual attributes."""

    class Outcome(models.TextChoices):
        COMPLETE = "complete", "Complete"
        INCOMPLETE = "incomplete", "Incomplete"
        OUT = "out", "Out"
        OFFSIDE = "offside", "Offside"
        UNKNOWN = "unknown", "Unknown"

    class Height(models.TextChoices):
        GROUND = "ground", "Ground"
        LOW = "low", "Low"
        HIGH = "high", "High"
        UNKNOWN = "unknown", "Unknown"

    class BodyPart(models.TextChoices):
        RIGHT_FOOT = "right_foot", "Right Foot"
        LEFT_FOOT = "left_foot", "Left Foot"
        HEAD = "head", "Head"
        CHEST = "chest", "Chest"
        OTHER = "other", "Other"

    class Technique(models.TextChoices):
        NORMAL = "normal", "Normal"
        HALF_VOLLEY = "half_volley", "Half Volley"
        VOLLEY = "volley", "Volley"
        LOB = "lob", "Lob"
        BACKHEEL = "backheel", "Backheel"
        OVERHEAD = "overhead", "Overhead"
        UNKNOWN = "unknown", "Unknown"

    class PassType(models.TextChoices):
        OPEN_PLAY = "open_play", "Open Play"
        FREE_KICK = "free_kick", "Free Kick"
        CORNER = "corner", "Corner"
        GOAL_KICK = "goal_kick", "Goal Kick"
        THROW_IN = "throw_in", "Throw In"
        KICK_OFF = "kick_off", "Kick Off"
        RECOVERY = "recovery", "Recovery"
        UNKNOWN = "unknown", "Unknown"

    external_event_id = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
    )
    event_index = models.PositiveIntegerField(default=0)
    period = models.PositiveIntegerField(default=1)
    possession = models.PositiveIntegerField(default=0)
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="passes",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="passes",
    )
    player = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="passes",
    )
    recipient = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="received_passes",
    )
    minute = models.PositiveIntegerField()
    second = models.PositiveIntegerField(default=0)
    x = models.FloatField()
    y = models.FloatField()
    end_x = models.FloatField()
    end_y = models.FloatField()
    length = models.FloatField(blank=True, null=True)
    angle = models.FloatField(blank=True, null=True)
    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
        default=Outcome.COMPLETE,
    )
    height = models.CharField(
        max_length=20,
        choices=Height.choices,
        default=Height.GROUND,
    )
    body_part = models.CharField(
        max_length=20,
        choices=BodyPart.choices,
        blank=True,
    )
    technique = models.CharField(
        max_length=20,
        choices=Technique.choices,
        blank=True,
    )
    pass_type = models.CharField(
        max_length=20,
        choices=PassType.choices,
        default=PassType.OPEN_PLAY,
    )
    play_pattern = models.CharField(max_length=50, blank=True)
    assisted_shot_event_id = models.CharField(max_length=64, blank=True)
    under_pressure = models.BooleanField(default=False)
    is_cross = models.BooleanField(default=False)
    is_cut_back = models.BooleanField(default=False)
    is_switch = models.BooleanField(default=False)
    is_through_ball = models.BooleanField(default=False)
    shot_assist = models.BooleanField(default=False)
    goal_assist = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.player or self.team} pass ({self.match.match_id} {self.minute}:{self.second:02d})"

    def clean(self):
        if not (0 <= self.x <= 120 and 0 <= self.y <= 80):
            raise ValidationError("Pass start coordinates out of bounds")

        if not (0 <= self.end_x <= 120 and 0 <= self.end_y <= 80):
            raise ValidationError("Pass end coordinates out of bounds")

        if self.team_id not in [self.match.home_team_id, self.match.away_team_id]:
            raise ValidationError("Pass team must be home or away team in this match")

        if self.recipient_id and self.player_id and self.recipient_id == self.player_id:
            raise ValidationError("Pass recipient cannot be the same as the passer")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["minute", "second", "id"]
        indexes = [
            models.Index(fields=["match"]),
            models.Index(fields=["team"]),
            models.Index(fields=["player"]),
            models.Index(fields=["recipient"]),
            models.Index(fields=["possession"]),
            models.Index(fields=["event_index"]),
            models.Index(fields=["minute", "second"]),
            models.Index(fields=["outcome"]),
            models.Index(fields=["pass_type"]),
            models.Index(fields=["shot_assist"]),
            models.Index(fields=["goal_assist"]),
        ]
