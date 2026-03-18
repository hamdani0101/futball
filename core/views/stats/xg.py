"""Views for expected-goals maps and shot visualization pages."""

import json

from django.core import serializers
from django.db.models import Count
from django.shortcuts import render

from core.models.match import Match
from core.models.shots import Shot
from core.models.team import Team
from analytics.services.xg.xg import build_xg_table
from core.views.selection import get_competition_season_selection


def xg_map_view(request):
    selection = get_competition_season_selection(request)
    competition = selection["selected_competition"]
    season = selection["selected_season"]

    xg_table = build_xg_table(season) if season else {}

    team_rows = []
    for stats in xg_table.values():
        matches = stats.get("matches", 0) or 0
        if matches <= 0:
            continue
        team_rows.append(
            {
                "team": stats["team_name"],
                "logo": stats["logo"],
                "matches": matches,
                "xgf_per_match": round(stats["xgf"] / matches, 2),
                "xga_per_match": round(stats["xga"] / matches, 2),
            }
        )

    for row in team_rows:
        row["xg_diff"] = round(row["xgf_per_match"] - row["xga_per_match"], 2)

    teams = [row["team"] for row in team_rows]
    xgf = [row["xgf_per_match"] for row in team_rows]
    xga = [row["xga_per_match"] for row in team_rows]
    avg_xgf = round(sum(xgf) / len(xgf), 2) if xgf else 0
    avg_xga = round(sum(xga) / len(xga), 2) if xga else 0
    top_attack = max(team_rows, key=lambda r: r["xgf_per_match"], default=None)
    best_defence = min(team_rows, key=lambda r: r["xga_per_match"], default=None)
    sorted_rows = sorted(team_rows, key=lambda r: r["xg_diff"], reverse=True)

    return render(
        request,
        "futball/stats/xg_map.html",
        {
            "competitions": selection["competitions"],
            "seasons": selection["seasons"],
            "season_json_data": selection["season_json_data"],
            "selected_competition": competition,
            "selected_season": season,
            "teams": teams,
            "xgf": xgf,
            "xga": xga,
            "team_rows": sorted_rows,
            "avg_xgf": avg_xgf,
            "avg_xga": avg_xga,
            "top_attack": top_attack,
            "best_defence": best_defence,
        },
    )


def xg_pitch_map_view(request):
    selection = get_competition_season_selection(request)
    seasons_all = selection["seasons_all"]
    seasons = selection["seasons"]
    team_id = request.GET.get("team")
    selected_competition = selection["selected_competition"]
    season_id = request.GET.get("season")

    if season_id:
        season = seasons.filter(id=season_id).first()
    else:
        season = (
            seasons.annotate(shot_count=Count("match__shots"))
            .order_by("-shot_count", "-id")
            .first()
        )

    matches = season.match_set.all() if season else Match.objects.none()

    shots = Shot.objects.filter(match__in=matches)

    teams_for_season = (
        Team.objects.filter(shots__match__in=matches)
        .distinct()
        .order_by("name")
    )

    teams_by_season = {}
    for s in seasons_all:
        season_teams = (
            Team.objects.filter(shots__match__season=s)
            .distinct()
            .order_by("name")
            .values("id", "name")
        )
        teams_by_season[str(s.id)] = list(season_teams)

    selected_team = None
    if team_id:
        shots = shots.filter(team_id=team_id)
        selected_team = teams_for_season.filter(id=team_id).first()

    shots_json = serializers.serialize(
        "json",
        shots,
        fields=("x", "y", "xg", "outcome"),
    )

    return render(
        request,
        "futball/stats/xg_pitch_map.html",
        {
            "competitions": selection["competitions"],
            "seasons": seasons,
            "teams": teams_for_season,
            "season_json_data": selection["season_json_data"],
            "teams_by_season": json.dumps(teams_by_season),
            "selected_competition": selected_competition,
            "selected_season": season,
            "shots_json": shots_json,
            "selected_team": selected_team,
            "total_shots": shots.count(),
        },
    )
