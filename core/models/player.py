"""Player and player-match relationship models."""

from django.db import models
from django.db.models import options
from django.utils import timezone

from core.models.team import Team

# Player model (Indonesian: Model pemain)
class Player(models.Model):
    external_id = models.IntegerField(unique=True, null=True, blank=True)
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

    @property
    def age(self):
        """Return the player's age in years when birth date is available."""
        if not self.birth_date:
            return None

        today = timezone.localdate()
        years = today.year - self.birth_date.year
        has_not_had_birthday = (today.month, today.day) < (
            self.birth_date.month,
            self.birth_date.day,
        )
        return years - int(has_not_had_birthday)
