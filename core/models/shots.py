"""Shot-level models used for xG and shooting analytics."""

from django.db import models
from django.core.exceptions import ValidationError
from core.models.event import Event
from core.models.match import Match
from core.models.team import Team
from core.models.player import Player

# Shot model (Indonesian: Model tembakan)
class Shot(models.Model):    
    
    class Outcome(models.TextChoices):
        GOAL = "goal", "Goal"
        SAVED = "saved", "Saved"
        SAVED_OFF_TARGET = "saved_off_target", "Saved Off Target"
        BLOCKED = "blocked", "Blocked"
        OFF_TARGET = "off_target", "Off Target"
        WAYWARD = "wayward", "Wayward"
        POST = "post", "Post"

    class BodyPart(models.TextChoices):
        RIGHT_FOOT = "right_foot", "Right Foot"
        LEFT_FOOT = "left_foot", "Left Foot"
        HEAD = "head", "Head"
        OTHER = "other", "Other"

    class ShotType(models.TextChoices):
        OPEN_PLAY = "open_play", "Open Play"
        PENALTY = "penalty", "Penalty"
        FREE_KICK = "free_kick", "Free Kick"
        
    class AssistType(models.TextChoices):
        CROSS = "cross", "Cross"
        THROUGH_BALL = "through_ball", "Through Ball"
        CUTBACK = "cutback", "Cutback"
        OTHER = "other", "Other"
    
    class PlayPattern(models.TextChoices):
        OPEN_PLAY = "open_play", "Open Play"
        CORNER = "corner", "Corner"
        FREE_KICK = "free_kick", "Free Kick"
        PENALTY = "penalty", "Penalty"

    event = models.OneToOneField(
        Event,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shot_detail",
    )
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="shots"
    )

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="shots"
    )
    minute = models.IntegerField()
    second = models.IntegerField(default=0)

    # StatsBomb style coordinates (0–120, 0–80) (Indonesian: Koordinat style StatsBomb (0–120, 0–80))
    x = models.FloatField()
    y = models.FloatField()

    xg = models.FloatField()
    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices
    )
    
    is_goal = models.BooleanField(default=False)

    body_part = models.CharField(
        max_length=20,
        choices=BodyPart.choices,
        blank=True
    )

    shot_type = models.CharField(
        max_length=20,
        choices=ShotType.choices,
        blank=True
    )
    player = models.ForeignKey(
        Player,
        null=True,
        on_delete=models.SET_NULL
    )
    assist_player = models.ForeignKey(
        Player,
        null=True,
        on_delete=models.SET_NULL,
        related_name="assisted_shots"
    )
    assist_type = models.CharField(
        max_length=20,
        choices=AssistType.choices,
        blank=True
    )
    shot_angle = models.FloatField(default=0)
    shot_distance = models.FloatField(default=0)
    under_pressure = models.BooleanField(default=False)
    defenders_in_between = models.IntegerField(default=0)
    gk_distance = models.FloatField(default=0)
    play_pattern = models.CharField(
        max_length=20,
        choices=PlayPattern.choices,
        blank=True
    )
    is_big_chance = models.BooleanField(default=False)
    period = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.team} shot ({self.xg})"

    # Validate coordinates and team (Indonesian: Validasi koordinat dan tim)
    def clean(self):
        if not (0 <= self.x <= 120 and 0 <= self.y <= 80):
            raise ValidationError("Shot coordinates out of bounds")

        if self.team not in [self.match.home_team, self.match.away_team]:
            raise ValidationError("Shot team must be home or away team")

        if self.event_id and self.event.match_id != self.match_id:
            raise ValidationError("Shot event must belong to the same match")

        if self.event_id and self.event.type != Event.Type.SHOT:
            raise ValidationError("Shot event must have type shot")

    # Ordering and indexes (Indonesian: Pengurutan dan indeks)
    class Meta:
        ordering = ["minute", "second"]
        indexes = [
            models.Index(fields=["match"]),
            models.Index(fields=["team"]),
        ]
