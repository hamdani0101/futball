"""Competition model definitions and related metadata."""

from django.db import models

# Competition model (Indonesian: Model kompetisi)
class Competition(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, blank=True)
    logo = models.ImageField(upload_to='competition/logos', blank=True, null=True)
    country = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name