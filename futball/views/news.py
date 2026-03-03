from django.shortcuts import get_object_or_404, render

from futball.models.news import News


def news_list(request):
    news = News.objects.all().order_by("-created_at")
    return render(request, "futball/news/news_list.html", {"news": news})


def news_detail(request, slug):
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
