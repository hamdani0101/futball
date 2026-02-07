from django.shortcuts import render
from django.core import serializers
from futball.services.standings import build_league_table
from futball.services.xg import build_xg_table
from futball.models.competition import Competition
from futball.models.match import Match
from futball.models.shots import Shot
from futball.models.season import Season

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
