"""Template context processors shared across the futball app.

These helpers provide data that should be available in many templates without
requiring each view to inject it explicitly.
"""

from django.core.cache import cache
from core.models.news import News

def global_base_data(request):
    """Return cached global template data used by the base layout.

    The current implementation exposes all ``News`` records so shared template
    fragments can render them consistently. The payload is cached for 30
    minutes because this context processor can run on every request.

    Args:
        request: The active ``HttpRequest`` provided by Django. It is not used
            directly right now, but Django context processors always receive it.

    Returns:
        dict: Template context entries that should be globally available.
    """
    data = cache.get("global_base_data")

    if not data:
        data = {
            "news": News.objects.all(),
        }
        cache.set("global_base_data", data, 60 * 30)

    return data
