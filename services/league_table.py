from collections import defaultdict
from analysis.models import Match


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

    matches = Match.objects.filter(season=season)

    for m in matches:
        home = m.home_team.name
        away = m.away_team.name

        table[home]["played"] += 1
        table[away]["played"] += 1

        table[home]["gf"] += m.home_score
        table[home]["ga"] += m.away_score
        table[away]["gf"] += m.away_score
        table[away]["ga"] += m.home_score

        if m.home_score > m.away_score:
            table[home]["win"] += 1
            table[away]["loss"] += 1
            table[home]["points"] += 3
        elif m.home_score < m.away_score:
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
