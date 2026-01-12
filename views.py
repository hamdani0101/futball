from django.shortcuts import render
from django.db.models import Sum
from analysis.models import Season
from analysis.services.league_table import build_league_table
from analysis.services.xg import build_xg_table
from analysis.models import Season, Match


def league_table_view(request):
    season = Season.objects.first()
    table = build_league_table(season)

    ranked_table = []
    for idx, (team, stats) in enumerate(table, start=1):
        ranked_table.append({
            "rank": idx,
            "team": team,
            **stats,
        })

    return render(
        request,
        "analysis/league_table.html",
        {
            "season": season,
            "table": ranked_table,
        },
    )



def xg_map_view(request):
    season = Season.objects.first()
    xg_table = build_xg_table(season)

    teams = []
    xgf = []
    xga = []

    for team, stats in xg_table.items():
        teams.append(team)
        xgf.append(round(stats["xgf"] / stats["matches"], 2))
        xga.append(round(stats["xga"] / stats["matches"], 2))

    return render(
        request,
        "analysis/xg_map.html",
        {
            "season": season,
            "teams": teams,
            "xgf": xgf,
            "xga": xga,
        },
    )

def dashboard_view(request):
    seasons = Season.objects.all().order_by("-name")

    # ambil season dari query param
    season_id = request.GET.get("season")

    if season_id:
        season = Season.objects.get(id=season_id)
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

    return render(
        request,
        "analysis/dashboard.html",
        {
            "seasons": seasons,
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
