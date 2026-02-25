from futball.models.match import Match
from futball.models.shots import Shot
from futball.services.xg import build_xg_table
from futball.services.standings import build_league_table

# Get season summary (Indonesian: Dapatkan ringkasan musim)
def get_season_summary(season):
    # If no season, return empty data (Indonesian: Jika tidak ada musim, kembalikan data kosong)
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

    # Get finished matches (Indonesian: Dapatkan pertandingan yang selesai)
    matches = Match.objects.filter(
        season=season,
        status="finished"
    )

    # Count matches (Indonesian: Hitung pertandingan)
    total_matches = matches.count()

    # Count goals (Indonesian: Hitung gol)
    total_goals = Shot.objects.filter(
        match__season=season,
        outcome="goal",
    ).count()

    # Average goals (Indonesian: Rata-rata gol)
    avg_goals = round(
        total_goals / total_matches, 2
    ) if total_matches else 0

    # standings (Indonesian: Standings)
    table = build_league_table(season)
    leader = table[0][0] if table else "-"

    # xG analytics (Indonesian: Analitik xG)
    xg_table = build_xg_table(season)

    # Top attack (Indonesian: Serangan terbaik)
    top_attack = max(
        xg_table,
        key=lambda team: xg_table[team]["xgf"],
        default="-"
    )

    # Best defence (Indonesian: Pertahanan terbaik)
    best_defence = min(
        xg_table,
        key=lambda team: xg_table[team]["xga"],
        default="-"
    )

    # Return summary (Indonesian: Kembalikan ringkasan)
    return {
        "total_matches": total_matches,
        "total_goals": total_goals,
        "avg_goals": avg_goals,
        "leader": leader,
        "top_attack": xg_table[top_attack]['team_name'],
        "best_defence": xg_table[best_defence]['team_name'],
        "top_5": table[:5],
        "bottom_3": table[-3:],
    }
