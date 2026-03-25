"""Shot-level models used for xG and shooting analytics."""

from django.db import models
from django.core.exceptions import ValidationError
from core.models.match import Match
from core.models.team import Team
from core.models.player import Player

# Shot model (Indonesian: Model tembakan)
class Shot(models.Model):    
    
    class OUTCOME(models.TextChoices):
        GOAL = "goal", "Goal"
        SAVED = "saved", "Saved"
        SAVED_OFF_TARGET = "saved_off_target", "Saved Off Target"
        BLOCKED = "blocked", "Blocked"
        OFF_TARGET = "off_target", "Off Target"
        WAYWARD = "wayward", "Wayward"
        POST = "post", "Post"

    class BODY_PART(models.TextChoices):
        RIGHT_FOOT = "right_foot", "Right Foot"
        LEFT_FOOT = "left_foot", "Left Foot"
        HEAD = "head", "Head"

    class SHOT_TYPE(models.TextChoices):
        OPEN_PLAY = "open_play", "Open Play"
        PENALTY = "penalty", "Penalty"
        FREE_KICK = "free_kick", "Free Kick"
        
    class ASSIST_TYPE(models.TextChoices):
        CROSS = "cross", "Cross"
        THROUGH_BALL = "through_ball", "Through Ball"
        CUTBACK = "cutback", "Cutback"
        OTHER = "other", "Other"
    
    class PLAY_PATTERN(models.TextChoices):
        OPEN_PLAY = "open_play", "Open Play"
        CORNER = "corner", "Corner"
        FREE_KICK = "free_kick", "Free Kick"
        PENALTY = "penalty", "Penalty"

    external_event_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
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
        choices=OUTCOME.choices
    )
    
    is_goal = models.BooleanField(default=False)

    body_part = models.CharField(
        max_length=20,
        choices=BODY_PART.choices,
        blank=True
    )

    shot_type = models.CharField(
        max_length=20,
        choices=SHOT_TYPE.choices,
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
        choices=ASSIST_TYPE.choices,
        blank=True
    )
    shot_angle = models.FloatField(default=0)
    shot_distance = models.FloatField(default=0)
    under_pressure = models.BooleanField(default=False)
    defenders_in_between = models.IntegerField(default=0)
    gk_distance = models.FloatField(default=0)
    play_pattern = models.CharField(
        max_length=20,
        choices=PLAY_PATTERN.choices,
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

    # Ordering and indexes (Indonesian: Pengurutan dan indeks)
    class Meta:
        ordering = ["minute", "second"]
        indexes = [
            models.Index(fields=["match"]),
            models.Index(fields=["team"]),
        ]
