from django.db import models


class Competition(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name


class Season(models.Model):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)  # e.g. "2023/2024"

    def __str__(self):
        return f"{self.competition} {self.name}"


class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)

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

    # 🔥 FIELD UNTUK xG
    home_shots = models.IntegerField(default=0)
    away_shots = models.IntegerField(default=0)
    home_shots_on_target = models.IntegerField(default=0)
    away_shots_on_target = models.IntegerField(default=0)



class Shot(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    minute = models.IntegerField()
    second = models.IntegerField(default=0)

    # StatsBomb style coordinates (0–120, 0–80)
    x = models.FloatField()
    y = models.FloatField()

    xg = models.FloatField()
    outcome = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.team} shot ({self.xg})"
