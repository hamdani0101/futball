"""Service layer for computing league standings and table rows."""

from collections import defaultdict
from futball.models.match import Match
from django.db.models import Count, Q, F

# Build league table (Indonesian: Bangun tabel liga)
def build_league_table(season):
    # If no season, return empty table (Indonesian: Jika tidak ada musim, kembalikan tabel kosong)
    if not season:
        return []


    # Initialize table (Indonesian: Inisialisasi tabel)
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

    # Get finished matches (Indonesian: Dapatkan pertandingan yang selesai)
    matches = (
        Match.objects
        .filter(
            season=season,
            status="finished"
        )
        .select_related("home_team", "away_team")
        .prefetch_related("team_stats")
    )


    # Process matches (Indonesian: Proses pertandingan)
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

        # goals for / against (Indonesian: Gol untuk / melawan)
        table[home]["gf"] += m.home_goals
        table[home]["ga"] += m.away_goals
        table[away]["gf"] += m.away_goals
        table[away]["ga"] += m.home_goals

        # result (Indonesian: Hasil)
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

    # Calculate goal difference (Indonesian: Hitung selisih gol)
    for team in table.values():
        team["gd"] = team["gf"] - team["ga"]

    # Sort by points, GD, GF (Indonesian: Urutkan berdasarkan poin, GD, GF)
    sorted_table = sorted(
        table.items(),
        key=lambda x: (x[1]["points"], x[1]["gd"], x[1]["gf"]),
        reverse=True,
    )

    # Return sorted table (Indonesian: Kembalikan tabel yang diurutkan)
    return sorted_table
