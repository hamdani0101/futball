"""Player and player-match relationship models."""

from django.db import models
from futball.models.team import Team
from futball.models.match import Match
from futball.models.player import Player

# Player match model (Indonesian: Model pertandingan pemain)
class PlayerMatch(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)

    is_starter = models.BooleanField(default=False)
    minute_on = models.IntegerField(default=0)
    minute_off = models.IntegerField(default=90)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Unique together player and match (Indonesian: Unik bersama pemain dan pertandingan)
    class Meta:
        unique_together = ("player", "match")
