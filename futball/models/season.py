from django.db import models
from futball.models.competition import Competition

class Season(models.Model):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.competition} {self.name}"
    
    class Meta:
        unique_together = ("competition", "name")