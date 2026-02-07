from collections import defaultdict
from futball.models.match import Match
from django.db.models import Count, Q, F

def build_league_table(season):
    table = defaultdict(lambda: {
        "played": 0,
        "win": 0,
        "draw": 0,
        "loss": 0,
        "gf": 0,
        "ga": 0,
        "gd": 0,
        "points": 0,
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
            )
        )
        .select_related("home_team", "away_team")
    )

    for m in matches:
        if getattr(m, "score", None) is not None:
            m.home_goals = m.score.home_goals
            m.away_goals = m.score.away_goals

        home = m.home_team.name
        away = m.away_team.name

        table[home]["played"] += 1
        table[away]["played"] += 1

        # goals for / against
        table[home]["gf"] += m.home_goals
        table[home]["ga"] += m.away_goals
        table[away]["gf"] += m.away_goals
        table[away]["ga"] += m.home_goals

        # result
        if m.home_goals > m.away_goals:
            table[home]["win"] += 1
            table[away]["loss"] += 1
            table[home]["points"] += 3

        elif m.home_goals < m.away_goals:
            table[away]["win"] += 1
            table[home]["loss"] += 1
            table[away]["points"] += 3

        else:
            table[home]["draw"] += 1
            table[away]["draw"] += 1
            table[home]["points"] += 1
            table[away]["points"] += 1


    for team in table.values():
        team["gd"] = team["gf"] - team["ga"]

    # Sort by points, GD, GF
    sorted_table = sorted(
        table.items(),
        key=lambda x: (x[1]["points"], x[1]["gd"], x[1]["gf"]),
        reverse=True,
    )

    return sorted_table
