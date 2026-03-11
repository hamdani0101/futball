"""Service utilities for generating season summary data."""

from futball.models.match import Match
from futball.models.shots import Shot
from futball.services.standings import build_league_table
from futball.services.xg import build_xg_table


def get_season_summary(season):
    if not season:
        return {
            "total_matches": 0,
            "total_goals": 0,
            "avg_goals": 0,
            "leader": "-",
            "top_attack": "-",
            "best_defence": "-",
            "top_5": [],
            "bottom_3": [],
        }

    matches = Match.objects.filter(season=season, status="finished")
    total_matches = matches.count()
    total_goals = Shot.objects.filter(match__season=season, outcome="goal").count()
    avg_goals = round(total_goals / total_matches, 2) if total_matches else 0

    table = build_league_table(season)
    if table:
        leader_name, leader_data = table[0]
        leaders = {
            "team_name": leader_name,
            "logo": leader_data.get("logo", "-"),
        }
    else:
        leaders = {
            "team_name": "-",
            "logo": "-",
        }

    xg_table = build_xg_table(season)
    if not xg_table:
        return {
            "total_matches": total_matches,
            "total_goals": total_goals,
            "avg_goals": avg_goals,
            "leader": leaders,
            "top_attack": {"team_name": "-", "logo": "-"},
            "best_defence": {"team_name": "-", "logo": "-"},
            "top_5": table[:5],
            "bottom_3": table[-3:],
        }

    top_attack = max(xg_table.values(), key=lambda team: team["xgf"])
    best_defence = min(xg_table.values(), key=lambda team: team["xga"])

    team_with_top_attack = {
        "team_name": top_attack["team_name"],
        "logo": top_attack["logo"] or "-",
    }
    team_with_best_defence = {
        "team_name": best_defence["team_name"],
        "logo": best_defence["logo"] or "-",
    }

    return {
        "total_matches": total_matches,
        "total_goals": total_goals,
        "avg_goals": avg_goals,
        "leader": leaders,
        "top_attack": team_with_top_attack,
        "best_defence": team_with_best_defence,
        "top_5": table[:5],
        "bottom_3": table[-3:],
    }
