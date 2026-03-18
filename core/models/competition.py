from django.db import models

class Gender(models.TextChoices):
    """
    Defines text-based choices for a model field.
    The first value is the actual value stored in the database.
    The second value is the human-readable label used in the admin and forms.
    """
    MALE = 'male', 'Male'
    FEMALE = 'female', 'Female'

class CompetitionFormat(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
# Competition model (Indonesian: Model kompetisi)
class Competition(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, blank=True)
    logo = models.ImageField(upload_to='competition/logos', blank=True)
    gender = models.CharField(max_length=20, choices=Gender.choices, blank=True)
    is_league = models.BooleanField(default=True)
    format = models.ForeignKey(CompetitionFormat, on_delete=models.CASCADE, related_name='competitions', null=True, blank=True)
    country = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name