"""News and media content models for the dashboard experience."""

from django.db import models

# News model (Indonesian: Model berita)
class News(models.Model):
    headline=models.CharField(max_length=155)
    slug = models.SlugField(max_length=155, unique=True)
    shortdesc=models.CharField(max_length=155)
    content=models.TextField()
    thumbnail = models.ImageField(upload_to="news/thumbnail/")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
# News content image model (Indonesian: Model gambar konten berita)
class NewsContentImage(models.Model):
    name_file= models.ImageField(upload_to="news/content/")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
