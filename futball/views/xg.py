import json
from django.shortcuts import render
from django.db.models import Count
from django.core import serializers
from futball.services.xg import build_xg_table
from futball.models.season import Season
from futball.models.match import  Match
from futball.models.competition import Competition
from futball.models.team import Team
from futball.models.shots import Shot

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