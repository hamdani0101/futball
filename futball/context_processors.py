"""Context processors that expose shared futball data to templates."""

from django.core.cache import cache
from futball.models.news import News

def global_base_data(request):
    data = cache.get("global_base_data")

    if not data:
        data = {
            "news": News.objects.all(),
        }
        cache.set("global_base_data", data, 60 * 30)

    return data