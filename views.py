import pprint
from django.shortcuts import render
from django.db.models import Sum
from django.core import serializers
from analysis.models import Season
from analysis.services.league_table import build_league_table
from analysis.services.xg import build_xg_table
from analysis.models import Season, Competition, Match


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


    match competition.name:
        case "Premier League":
            champions_league_places = 4
            europa_league_places = 2
            conference_league_places = 1
            relegation_places = 3

        case "La Liga":
            champions_league_places = 4
            europa_league_places = 2
            conference_league_places = 1
            relegation_places = 3

        case "Bundesliga":
            champions_league_places = 4
            europa_league_places = 2
            conference_league_places = 1
            relegation_places = 3

        case "Serie A":
            champions_league_places = 4
            europa_league_places = 2
            conference_league_places = 1
            relegation_places = 3

        case "Ligue 1":
            champions_league_places = 3 
            europa_league_places = 1
            conference_league_places = 1
            relegation_places = 3       

        case _:
            champions_league_places = 0
            europa_league_places = 0
            conference_league_places = 0
            relegation_places = 3


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
        "analysis/league_table.html",
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



def xg_map_view(request):
    competitions = Competition.objects.all().order_by("name")
    seasons_all = Season.objects.all().order_by("-name")

    # ambil season dari query param
    competition_id = request.GET.get("competition")
    season_id = request.GET.get("season")

    if competition_id:
        seasons = seasons_all.filter(competition__id=competition_id)
    else:
        competition = competitions.first()
        seasons = seasons_all.filter(competition=competition)

    if season_id:
        season = seasons.get(id=season_id)
    else:
        season = seasons.first()

    xg_table = build_xg_table(season)

    teams = []
    xgf = []
    xga = []

    for team, stats in xg_table.items():
        teams.append(team)
        xgf.append(round(stats["xgf"] / stats["matches"], 2))
        xga.append(round(stats["xga"] / stats["matches"], 2))

    season_json_data = serializers.serialize("json", seasons_all.all())

    return render(
        request,
        "analysis/xg_map.html",
        {
            "competitions": competitions,
            "seasons": seasons,
            "season_json_data": season_json_data,
            "selected_competition": season.competition,
            "selected_season": season,
            "teams": teams,
            "xgf": xgf,
            "xga": xga,
        },
    )

def dashboard_view(request):
    competitions = Competition.objects.all().order_by("name")
    seasons_all = Season.objects.all().order_by("-name")

    # ambil season dari query param
    competition_id = request.GET.get("competition")
    season_id = request.GET.get("season")

    #kuota champions league berdasarkan liga

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

    matches = Match.objects.filter(season=season)
    total_matches = matches.count()

    total_goals = matches.aggregate(
        goals=Sum("home_score") + Sum("away_score")
    )["goals"] or 0

    avg_goals = round(total_goals / total_matches, 2) if total_matches else 0

    table = build_league_table(season)
    leader = table[0][0] if table else "-"

    xg_table = build_xg_table(season)

    top_attack = max(
        xg_table.items(),
        key=lambda x: x[1]["xgf"],
        default=("-", {}),
    )[0]

    best_defence = min(
        xg_table.items(),
        key=lambda x: x[1]["xga"],
        default=("-", {}),
    )[0]

    season_json_data = serializers.serialize("json", seasons_all.all())

    return render(
        request,
        "analysis/dashboard.html",
        {
            "competitions": competitions,
            "seasons": seasons,
            "season_json_data": season_json_data,
            "selected_competition": season.competition,
            "selected_season": season,
            "total_matches": total_matches,
            "total_goals": total_goals,
            "avg_goals": avg_goals,
            "leader": leader,
            "top_attack": top_attack,
            "best_defence": best_defence,
            "top_5": table[:5],
            "bottom_3": table[-3:],
        },
    )
