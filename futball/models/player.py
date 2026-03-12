"""Player and player-match relationship models."""

from django.db import models
from futball.models.team import Team

# Player model (Indonesian: Model pemain)
class Player(models.Model):
    external_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='player/photos', blank=True, null=True)
    country = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(blank=True, null=True)
    team_now = models.ForeignKey(Team, on_delete=models.CASCADE)
    position = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name