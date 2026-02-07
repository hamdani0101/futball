from collections import defaultdict
from futball.models.match import Match
from django.db.models import Count, Q, F

def build_xg_table(season):
    table = defaultdict(lambda: {
        "xgf": 0.0,
        "xga": 0.0,
        "gf": 0,
        "ga": 0,
        "matches": 0,
    })

    matches = (
        Match.objects
        .filter(season=season, status="finished")
        .annotate(
            home_goals=Count(
                "shots",
                filter=Q(
                    shots__team=F("home_team"),
                    shots__outcome="goal"
                )
            ),
            away_goals=Count(
                "shots",
                filter=Q(
                    shots__team=F("away_team"),
                    shots__outcome="goal"
                )
            ),
        )
        .select_related("home_team", "away_team")
        .prefetch_related("team_stats")
    )

    for m in matches:
        home = m.home_team.name
        away = m.away_team.name

        stats_by_team = {s.team_id: s for s in m.team_stats.all()}
        home_stats = stats_by_team.get(m.home_team_id)
        away_stats = stats_by_team.get(m.away_team_id)

        hg = m.home_goals or 0
        ag = m.away_goals or 0
        hxg = home_stats.xg if home_stats else 0.0
        axg = away_stats.xg if away_stats else 0.0

        table[home]["matches"] += 1
        table[away]["matches"] += 1

        table[home]["gf"] += hg
        table[home]["ga"] += ag
        table[away]["gf"] += ag
        table[away]["ga"] += hg

        table[home]["xgf"] += hxg
        table[home]["xga"] += axg
        table[away]["xgf"] += axg
        table[away]["xga"] += hxg

    return table
