from collections import defaultdict
from django.db.models import Count, Q, F, Sum
from futball.models.match import Match
from futball.models.shots import Shot


def build_xg_table(season):
    table = defaultdict(lambda: {
        "team_id": None,
        "team_name": "",
        "matches": 0,
        "gf": 0,
        "ga": 0,
        "xgf": 0.0,
        "xga": 0.0,
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
            home_xg=Sum(
                "shots__xg",
                filter=Q(shots__team=F("home_team"))
            ),
            away_xg=Sum(
                "shots__xg",
                filter=Q(shots__team=F("away_team"))
            ),
        )
        .select_related("home_team", "away_team")
    )

    for m in matches:
        home = m.home_team
        away = m.away_team

        hg = m.home_goals or 0
        ag = m.away_goals or 0
        hxg = m.home_xg or 0.0
        axg = m.away_xg or 0.0

        for team, gf, ga, xgf, xga in [
            (home, hg, ag, hxg, axg),
            (away, ag, hg, axg, hxg),
        ]:
            t = table[team.id]
            t["team_id"] = team.id
            t["team_name"] = team.name
            t["matches"] += 1
            t["gf"] += gf
            t["ga"] += ga
            t["xgf"] += xgf
            t["xga"] += xga

    return table
