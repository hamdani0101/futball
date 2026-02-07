from django.db import models
from django.core.exceptions import ValidationError


class Competition(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Season(models.Model):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.competition} {self.name}"
    
    class Meta:
        unique_together = ("competition", "name")



class Team(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

    class Meta:
        unique_together = ("name", "country")

class Match(models.Model):
    match_id = models.CharField(max_length=100, unique=True)
    season = models.ForeignKey(Season, on_delete=models.CASCADE)
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="home_matches")
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="away_matches")
    match_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=[
            ("scheduled", "Scheduled"),
            ("finished", "Finished"),
            ("postponed", "Postponed"),
        ],
        default="scheduled"
    )
    
    def __str__(self):
        return f"{self.home_team} vs {self.away_team} ({self.match_date.date()})"
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.home_team == self.away_team:
            raise ValidationError("Home and away team cannot be the same")
        
    class Meta:
        ordering = ["-match_date"]
        indexes = [
            models.Index(fields=["season"]),
            models.Index(fields=["home_team"]),
            models.Index(fields=["away_team"]),
            models.Index(fields=["status"]),
        ]


class MatchScore(models.Model):
    match = models.OneToOneField(
        Match,
        on_delete=models.CASCADE,
        related_name="score",
    )
    home_goals = models.IntegerField(default=0)
    away_goals = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.match} {self.home_goals}-{self.away_goals}"


class MatchTeamStats(models.Model):
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="team_stats"
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    xg = models.FloatField(default=0)
    shots = models.IntegerField(default=0)
    shots_on_target = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def clean(self):
        if self.team not in [self.match.home_team, self.match.away_team]:
            raise ValidationError("Team must be home or away team in this match")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    
    class Meta:
        unique_together = ("match", "team")

class Shot(models.Model):    
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

    # StatsBomb style coordinates (0–120, 0–80)
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.team} shot ({self.xg})"
    
    def save(self, *args, **kwargs):
        self.is_goal = self.outcome == "goal"
        self.clean()
        super().save(*args, **kwargs)

    def clean(self):
        if not (0 <= self.x <= 120 and 0 <= self.y <= 80):
            raise ValidationError("Shot coordinates out of bounds")

        if self.team not in [self.match.home_team, self.match.away_team]:
            raise ValidationError("Shot team must be home or away team")

    
    class Meta:
        ordering = ["minute", "second"]
        indexes = [
            models.Index(fields=["match"]),
            models.Index(fields=["team"]),
        ]


class Player(models.Model):
    external_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    position = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class PlayerMatch(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)

    is_starter = models.BooleanField(default=False)
    minute_on = models.IntegerField(default=0)
    minute_off = models.IntegerField(default=90)

    class Meta:
        unique_together = ("player", "match")

class News(models.Model):
    headline=models.CharField(max_length=155)
    shortdesc=models.CharField(max_length=155)
    content=models.TextField()
    thumbnail = models.ImageField(upload_to="news/thumbnail/")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class NewsContentImage(models.Model):
    name_file= models.ImageField(upload_to="news/content/")
