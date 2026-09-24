from django.db import models
from core.models.event import Event
from core.models.match import Match
from core.models.team import Team
from core.models.player import Player
from core.models.shots import Shot

class Save(models.Model):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name="save_detail")
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    originating_shot = models.ForeignKey(Shot, on_delete=models.SET_NULL, null=True, blank=True, related_name="saves")
    minute = models.PositiveIntegerField()
    second = models.PositiveIntegerField()
    
    class Meta:
        indexes = [models.Index(fields=["match", "minute", "second"])]
