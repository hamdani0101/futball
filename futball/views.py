import pprint
import json
from django.http import HttpResponse
from django.shortcuts import render
from django.db.models import Sum, Count, Q
from django.core import serializers
from futball.models import Season
from futball.services.league_table import build_league_table
from futball.services.xg import build_xg_table
from futball.models import Season, Competition, Match, Team, Shot


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
        "futball/xg_map.html",
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
    
def xg_pitch_map_view(request):
    competitions = Competition.objects.all().order_by("name")
    seasons_all = Season.objects.all().order_by("-name")
    teams_all = Team.objects.all().order_by("name")

    competition_id = request.GET.get("competition")
    season_id = request.GET.get("season")
    team_id = request.GET.get("team")

    season_json_data = serializers.serialize("json", seasons_all.all())

    selected_competition = (
        competitions.filter(id=competition_id).first() if competition_id else competitions.first()
    )

    seasons = (
        seasons_all.filter(competition=selected_competition)
        if selected_competition
        else seasons_all.none()
    )

    # pilih season dengan shots terbanyak jika belum dipilih
    if season_id:
        season = seasons.filter(id=season_id).first()
    else:
        season = (
            seasons.annotate(shot_count=Count("match__shots"))
            .order_by("-shot_count", "-id")
            .first()
        )

    # ambil semua match di season
    matches = season.match_set.all() if season else Match.objects.none()

    # base queryset shot
    shots = Shot.objects.filter(match__in=matches)

    # teams yang relevan dengan season (dan optional team filter nanti)
    teams_for_season = (
        Team.objects.filter(shots__match__in=matches)
        .distinct()
        .order_by("name")
    )

    # mapping season -> teams (semua season), untuk update dropdown di frontend
    teams_by_season = {}
    for s in seasons_all:
        season_teams = (
            Team.objects.filter(shots__match__season=s)
            .distinct()
            .order_by("name")
            .values("id", "name")
        )
        teams_by_season[str(s.id)] = list(season_teams)

    # filter team (opsional)
    selected_team = None
    if team_id:
        shots = shots.filter(team_id=team_id)
        selected_team = teams_for_season.filter(id=team_id).first()

    # serialize shots → frontend
    shots_json = serializers.serialize(
        "json",
        shots,
        fields=("x", "y", "xg", "outcome")
    )

    return render(
        request,
        "futball/xg_pitch_map.html",
        {
            "competitions": competitions,
            "seasons": seasons,
            "teams": teams_for_season,
            "season_json_data": season_json_data,
            "teams_by_season": json.dumps(teams_by_season),
            "selected_competition": selected_competition,
            "selected_season": season,
            "shots_json": shots_json,
            "selected_team": selected_team,
            "total_shots": shots.count(),
        },
    )

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

    matches = Match.objects.filter(season=season, status="finished")
    total_matches = matches.count()

    total_goals = Shot.objects.filter(
        match__in=matches,
        outcome="goal",
    ).count()


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
        "futball/dashboard.html",
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
