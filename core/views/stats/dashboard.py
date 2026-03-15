"""Dashboard views that assemble top-level league and news context."""

from django.shortcuts import render

from core.services.season_summary import get_season_summary
from core.services.xg import build_xg_table
from core.views.selection import get_competition_season_selection


def dashboard_view(request):
    selection = get_competition_season_selection(request)
    competition = selection["selected_competition"]
    season = selection["selected_season"]

    data = {
        "competitions": selection["competitions"],
        "seasons": selection["seasons"],
        "selected_competition": competition,
        "selected_season": season,
        "season_json_data": selection["season_json_data"],
        "total_matches": 0,
        "total_goals": 0,
        "avg_goals": 0,
        "leader": "-",
        "top_attack": "-",
        "best_defence": "-",
        "top_5": [],
        "bottom_3": [],
        "xg_teams": [],
        "xg_xgf": [],
        "xg_xga": [],
        "xg_team_rows": [],
        "xg_avg_xgf": 0,
        "xg_avg_xga": 0,
        "xg_top_attack": None,
        "xg_best_defence": None,
    }
    if season:
        data.update(get_season_summary(season))

        xg_table = build_xg_table(season)
        xg_rows = []
        for stats in xg_table.values():
            matches = stats.get("matches", 0) or 0
            if matches <= 0:
                continue
            row = {
                "team": stats["team_name"],
                "logo": stats["logo"],
                "xgf_per_match": round(stats["xgf"] / matches, 2),
                "xga_per_match": round(stats["xga"] / matches, 2),
            }
            row["xg_diff"] = round(row["xgf_per_match"] - row["xga_per_match"], 2)
            xg_rows.append(row)

        xg_rows_sorted = sorted(xg_rows, key=lambda r: r["xg_diff"], reverse=True)
        data["xg_teams"] = [r["team"] for r in xg_rows]
        data["xg_xgf"] = [r["xgf_per_match"] for r in xg_rows]
        data["xg_xga"] = [r["xga_per_match"] for r in xg_rows]
        data["xg_team_rows"] = xg_rows_sorted
        data["xg_avg_xgf"] = (
            round(sum(data["xg_xgf"]) / len(data["xg_xgf"]), 2) if data["xg_xgf"] else 0
        )
        data["xg_avg_xga"] = (
            round(sum(data["xg_xga"]) / len(data["xg_xga"]), 2) if data["xg_xga"] else 0
        )
        data["xg_top_attack"] = max(xg_rows, key=lambda r: r["xgf_per_match"], default=None)
        data["xg_best_defence"] = min(xg_rows, key=lambda r: r["xga_per_match"], default=None)

    return render(request, "futball/stats/dashboard.html", data)
