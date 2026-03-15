"""Service utilities for generating season summary data."""
from typing import Dict, Any
from core.models.match import Match
from core.models.shots import Shot
from core.services.standings import build_league_table
from core.services.xg import build_xg_table


EMPTY_TEAM = {"team_name": "-", "logo": "-"}

def empty_team() -> Dict[str, str]:
    return EMPTY_TEAM.copy()

def get_season_summary(season) -> Dict[str, Any]:
    if not season:
        return {
            "total_matches": 0,
            "total_goals": 0,
            "avg_goals": 0,
            "leader": empty_team(),
            "top_attack": empty_team(),
            "best_defence": empty_team(),
            "top_5": [],
            "bottom_3": [],
        }

    matches = Match.objects.filter(season=season, status="finished")
    total_matches = matches.count()

    total_goals = Shot.objects.filter(
        match__in=matches,
        outcome="goal"
    ).count()

    avg_goals = round(total_goals / total_matches, 2) if total_matches else 0

    table = build_league_table(season)

    leader = empty_team()
    if table:
        leader_name, leader_data = table[0]
        leader = {
            "team_name": leader_name,
            "logo": leader_data.get("logo", "-"),
        }

    top_attack = empty_team()
    best_defence = empty_team()

    xg_table = build_xg_table(season)

    if xg_table:
        attack = max(xg_table.values(), key=lambda t: t["xgf"])
        defence = min(xg_table.values(), key=lambda t: t["xga"])

        top_attack = {
            "team_name": attack["team_name"],
            "logo": attack["logo"] or "-",
        }

        best_defence = {
            "team_name": defence["team_name"],
            "logo": defence["logo"] or "-",
        }

    return {
        "total_matches": total_matches,
        "total_goals": total_goals,
        "avg_goals": avg_goals,
        "leader": leader,
        "top_attack": top_attack,
        "best_defence": best_defence,
        "top_5": table[:5] if table else [],
        "bottom_3": table[-3:] if table else [],
    }