"""Team model definitions, identity mapping, and assets."""

from django.db import models
from .stadium import Stadium


# Team model (Indonesian: Model tim)
class Team(models.Model):
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to="team/logos/", blank=True, null=True)
    home_stadium = models.ForeignKey(Stadium, on_delete=models.CASCADE, related_name='teams', null=True, blank=True)
    country = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

    # Unique together name and country (Indonesian: Unik bersama nama dan negara)
    class Meta:
        unique_together = ("name", "country")
