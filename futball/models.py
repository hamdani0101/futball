from django.db import models


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


class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Match(models.Model):
    match_id = models.CharField(max_length=100, unique=True)
    season = models.ForeignKey(Season, on_delete=models.CASCADE)
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="home_matches")
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="away_matches")
    match_date = models.DateField()

    home_score = models.IntegerField(default=0)
    away_score = models.IntegerField(default=0)

    home_shots = models.IntegerField(default=0)
    away_shots = models.IntegerField(default=0)
    home_shots_on_target = models.IntegerField(default=0)
    away_shots_on_target = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.team} shot ({self.xg})"


class News(models.Model):
    headline=models.CharField(max_length=155)
    shortdesc=models.CharField(max_length=155)
    content=models.TextField()
    thumbnail=models.CharField(max_length=155)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)