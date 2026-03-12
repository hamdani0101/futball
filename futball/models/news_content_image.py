"""News content image model (Indonesian: Model gambar konten berita)"""

from django.db import models

class NewsContentImage(models.Model):
    name_file = models.ImageField(upload_to="news/content/")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)