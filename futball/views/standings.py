import re
from django.shortcuts import render
from django.http import HttpResponse
from django.core import serializers
from futball.services.standings import build_league_table
from futball.models.season import Season
from futball.models.competition import Competition


def normalize_competition_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"\(.*?\)", "", name)   # hapus (football)
    name = re.sub(r"[^a-z\s]", "", name)  # hapus simbol
    return name.strip()

def league_table_view(request):
    competitions = Competition.objects.all().order_by("name")
    seasons_all = Season.objects.all().order_by("-name")

    # ambil season dari query param
    competition_id = request.GET.get("competition")
    season_id = request.GET.get("season")
    

    if competition_id:
        competition = competitions.get(id=competition_id)
        seasons = seasons_all.filter(competition=competition)
    else:
        competition = competitions.first()
        seasons = seasons_all.filter(competition=competition)

    COMPETITION_ALIAS = {
        "premier league": "epl",
        "english premier league": "epl",
        "epl": "epl",

        "la liga": "laliga",
        "liga bbva": "laliga",
        "spanish la liga": "laliga",

        "bundesliga": "bundesliga",
        "german bundesliga": "bundesliga",

        "serie a": "seriea",
        "italian serie a": "seriea",

        "ligue 1": "ligue1",
        "french ligue 1": "ligue1",
        "french ligue": "ligue1",
    }

    UEFA_RULES = {
        "epl": dict(cl=4, el=2, ecl=1, relegation=3),
        "laliga": dict(cl=4, el=2, ecl=1, relegation=3),
        "bundesliga": dict(cl=4, el=2, ecl=1, relegation=3),
        "seriea": dict(cl=4, el=2, ecl=1, relegation=3),
        "ligue1": dict(cl=3, el=1, ecl=1, relegation=3),
    }
    
    key = normalize_competition_name(competition.name)
    alias = COMPETITION_ALIAS.get(key)

    rules = UEFA_RULES.get(
        alias,
        dict(cl=0, el=0, ecl=0, relegation=3)
    )


    champions_league_places = rules["cl"]
    europa_league_places = rules["el"]
    conference_league_places = rules["ecl"]
    relegation_places = rules["relegation"]


    if season_id:
        season = seasons.get(id=season_id)
    else:
        season = seasons.first()

    table = build_league_table(season)

    ranked_table = []
    for idx, (team, stats) in enumerate(table, start=1):
        ranked_table.append({
            "rank": idx,
            "team": team,
            **stats,
        })

    season_json_data = serializers.serialize("json", seasons_all.all())

    relegation_cutoff = len(ranked_table) - relegation_places
    champions_league_cutoff = champions_league_places
    europa_league_cutoff = champions_league_places + europa_league_places
    conference_league_cutoff = champions_league_places + europa_league_places + conference_league_places
    
    return render(
        request,
        "futball/league_table.html",
        {
            "competitions": competitions,
            "seasons": seasons,
            "season_json_data": season_json_data,
            "selected_competition": season.competition,
            "selected_season": season,
            "table": ranked_table,
            "relegation_cutoff": relegation_cutoff,
            "champions_league_cutoff": champions_league_cutoff,
            "europa_league_cutoff": europa_league_cutoff,
            "conference_league_cutoff": conference_league_cutoff,
        },
    )
