from futball.models.match import Match
from futball.models.shots import Shot
from futball.services.xg import build_xg_table
from futball.services.standings import build_league_table


def get_season_summary(season):
    matches = Match.objects.filter(
        season=season,
        status="finished"
    )

    total_matches = matches.count()

    total_goals = Shot.objects.filter(
        match__season=season,
        outcome="goal",
    ).count()

    avg_goals = round(
        total_goals / total_matches, 2
    ) if total_matches else 0

    # standings
    table = build_league_table(season)
    leader = table[0][0] if table else "-"

    # xG analytics
    xg_table = build_xg_table(season)

    top_attack = max(
        xg_table,
        key=lambda team: xg_table[team]["xgf"],
        default="-"
    )

    best_defence = min(
        xg_table,
        key=lambda team: xg_table[team]["xga"],
        default="-"
    )

    return {
        "total_matches": total_matches,
        "total_goals": total_goals,
        "avg_goals": avg_goals,
        "leader": leader,
        "top_attack": top_attack,
        "best_defence": best_defence,
        "top_5": table[:5],
        "bottom_3": table[-3:],
    }
