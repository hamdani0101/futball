from django.db import models

class News(models.Model):
    headline=models.CharField(max_length=155)
    shortdesc=models.CharField(max_length=155)
    content=models.TextField()
    thumbnail = models.ImageField(upload_to="news/thumbnail/")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class NewsContentImage(models.Model):
    name_file= models.ImageField(upload_to="news/content/")
