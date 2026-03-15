"""Views for listing news articles and rendering article detail pages."""

from django.shortcuts import get_object_or_404, render

from core.models.news import News


def news_list(request):
    """Render the news index ordered from newest to oldest."""
    news = News.objects.all().order_by("-created_at")
    return render(request, "futball/news/news_list.html", {"news": news})


def news_detail(request, slug):
    """Render a single news article with a small related-news sidebar.

    Args:
        request: The active Django ``HttpRequest``.
        slug: The article slug used to look up the requested story.

    Returns:
        HttpResponse: The rendered ``futball/news/news_detail.html`` response.
    """
    article = get_object_or_404(News, slug=slug)
    latest_news = News.objects.exclude(pk=article.pk).order_by("-created_at")[:4]
    return render(
        request,
        "futball/news/news_detail.html",
        {
            "article": article,
            "news": latest_news,
        },
    )
