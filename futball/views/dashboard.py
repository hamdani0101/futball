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

    if competition_id:
        competition = competitions.get(id=competition_id)
        seasons = seasons_all.filter(competition=competition)
    else:
        competition = competitions.first()
        seasons = seasons_all.filter(competition=competition)

    if season_id:
        season = seasons.get(id=season_id)
    else:
        season = seasons.first()

    data = get_season_summary(season)
    data.update(
        {
            "competitions": competitions,
            "seasons": seasons,
            "selected_competition": competition,
            "selected_season": season,
            "season_json_data": serialize("json", seasons_all),
        }
    )
    return render(request, "futball/dashboard.html", data)


    
