from django.db import models
from futball.models.team import Team
from futball.models.match import Match

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
