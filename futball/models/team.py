from django.db import models


# Team model (Indonesian: Model tim)
class Team(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

    # Unique together name and country (Indonesian: Unik bersama nama dan negara)
    class Meta:
        unique_together = ("name", "country")
