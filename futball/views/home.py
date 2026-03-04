"""Landing page view for the futball app."""

from django.shortcuts import render

from futball.models.competition import Competition
from futball.models.match import Match
from futball.models.news import News
from futball.models.season import Season
from futball.models.team import Team


def home_view(request):
    latest_news = News.objects.all().order_by("-created_at")[:4]
    context = {
        "total_competitions": Competition.objects.count(),
        "total_seasons": Season.objects.count(),
        "total_teams": Team.objects.count(),
        "upcoming_matches": Match.objects.filter(status="scheduled").count(),
        "news": latest_news,
    }
    return render(request, "futball/home.html", context)

