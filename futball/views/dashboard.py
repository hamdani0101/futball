from django.core.serializers import serialize
from django.shortcuts import render
from futball.models.competition import Competition
from futball.models.season import Season
from futball.services.season_summary import get_season_summary

def dashboard_view(request):
    competitions = Competition.objects.all().order_by("name")
    seasons_all = Season.objects.all().order_by("-name")

    competition_id = request.GET.get("competition")
    season_id = request.GET.get("season")

    competition = (
        competitions.filter(id=competition_id).first()
        if competition_id
        else competitions.first()
    )
    seasons = seasons_all.filter(competition=competition) if competition else Season.objects.none()
    season = (
        seasons.filter(id=season_id).first()
        if season_id
        else seasons.first()
    )

    data = {
        "competitions": competitions,
        "seasons": seasons,
        "selected_competition": competition,
        "selected_season": season,
        "season_json_data": serialize("json", seasons_all),
        "total_matches": 0,
        "total_goals": 0,
        "avg_goals": 0,
        "leader": "-",
        "top_attack": "-",
        "best_defence": "-",
        "top_5": [],
        "bottom_3": [],
    }
    if season:
        data.update(get_season_summary(season))

    return render(request, "futball/dashboard.html", data)


    
