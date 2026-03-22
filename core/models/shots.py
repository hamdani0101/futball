"""Shot-level models used for xG and shooting analytics."""

from django.db import models
from django.core.exceptions import ValidationError
from core.models.match import Match
from core.models.team import Team
from core.models.player import Player

# Shot model (Indonesian: Model tembakan)
class Shot(models.Model):    
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
    SHOT_OUTCOME = [
        ("goal", "Goal"),
        ("saved", "Saved"),
        ("blocked", "Blocked"),
        ("off_target", "Off Target"),
    ]

    outcome = models.CharField(
        max_length=20,
        choices=SHOT_OUTCOME
    )
    
    is_goal = models.BooleanField(default=False)

    body_part = models.CharField(
        max_length=20,
        choices=[
            ("right_foot", "Right Foot"),
            ("left_foot", "Left Foot"),
            ("head", "Head"),
        ],
        blank=True
    )

    shot_type = models.CharField(
        max_length=20,
        choices=[
            ("open_play", "Open Play"),
            ("penalty", "Penalty"),
            ("free_kick", "Free Kick"),
        ],
        blank=True
    )
    player = models.ForeignKey(
        Player,
        null=True,
        on_delete=models.SET_NULL
    )
    period = models.IntegerField()
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
