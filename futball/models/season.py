"""Season model definitions for organizing competitions over time."""

from django.db import models
from futball.models.competition import Competition

# Season model (Indonesian: Model musim)
class Season(models.Model):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.competition} {self.name}"
    
    # Unique together competition and name (Indonesian: Unik bersama kompetisi dan nama)
    class Meta:
        unique_together = ("competition", "name")