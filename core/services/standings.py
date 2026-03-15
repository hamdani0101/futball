"""Utilities for building a season league table from finished matches.

The table is computed from ``Match`` records in a given season with
``status="finished"`` and team-level stats stored in ``team_stats``.
Each row includes common standings metrics such as wins, draws, losses,
goals for/against, goal difference, and points.
"""

from collections import defaultdict

from core.models.match import Match


def build_league_table(season):
    """Return sorted standings rows for a season.

    Args:
        season: Season instance used to filter matches.

    Returns:
        list[tuple[str, dict]]: A descending sorted list of ``(team_name, row)``
        where each ``row`` has:
        ``played``, ``win``, ``draw``, ``loss``, ``gf``, ``ga``, ``gd``,
        ``points``, and ``logo``.

    Notes:
        Sorting priority is points, then goal difference, then goals scored.
    """
    if not season:
        return []

    # Default row values for teams encountered in finished matches.
    table = defaultdict(lambda: {
        "played": 0,
        "win": 0,
        "draw": 0,
        "loss": 0,
        "gf": 0,
        "ga": 0,
        "gd": 0,
        "points": 0,
        "logo": None,
    })

    matches = (
        Match.objects
        .filter(
            season=season,
            status="finished"
        )
        .select_related("home_team", "away_team")
        .prefetch_related("team_stats")
    )

    # Aggregate per-match goals and apply result rules to both teams.
    for m in matches:
        home_goals = 0
        away_goals = 0

        for stat in m.team_stats.all():
            if stat.team_id == m.home_team_id:
                home_goals = stat.goals
            elif stat.team_id == m.away_team_id:
                away_goals = stat.goals

        m.home_goals = home_goals
        m.away_goals = away_goals

        home = m.home_team.name
        away = m.away_team.name
        
        home_team_logo = m.home_team.logo
        away_team_logo = m.away_team.logo

        table[home]["played"] += 1
        table[away]["played"] += 1

        # Update goals for/against.
        table[home]["gf"] += m.home_goals
        table[home]["ga"] += m.away_goals
        table[away]["gf"] += m.away_goals
        table[away]["ga"] += m.home_goals

        # Apply win/draw/loss and points.
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

        table[home]["logo"] = home_team_logo
        table[away]["logo"] = away_team_logo

    # Finalize goal difference after processing all matches.
    for team in table.values():
        team["gd"] = team["gf"] - team["ga"]

    # Sort by points, goal difference, and goals for (descending).
    sorted_table = sorted(
        table.items(),
        key=lambda x: (x[1]["points"], x[1]["gd"], x[1]["gf"]),
        reverse=True,
    )

    return sorted_table
