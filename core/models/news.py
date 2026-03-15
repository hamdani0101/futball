"""News and media content models for the dashboard experience."""

from django.db import models

# News model (Indonesian: Model berita)
class News(models.Model):
    headline=models.CharField(max_length=155)
    slug = models.SlugField(max_length=155, unique=True, null=True)
    shortdesc=models.CharField(max_length=155)
    content=models.TextField()
    hot_topic=models.BooleanField(default=False)
    thumbnail = models.ImageField(upload_to="news/thumbnail/")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
