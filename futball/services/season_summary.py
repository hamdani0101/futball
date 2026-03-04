"""Service utilities for generating season summary data."""

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
    if table:
        # Sort by points (descending)
        sorted_table = sorted(
            table,
            key=lambda x: x[1]['points'],
            reverse=True
        )

        leader_name, leader_data = sorted_table[0]

        leaders = {
            'team_name': leader_name,
            'logo': leader_data.get('logo', '-')
        }
    else:
        leaders = {
            'team_name': '-',
            'logo': '-'
        }

    # xG analytics (Indonesian: Analitik xG)
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
    
    top_attack = xg_table[top_attack]
    best_defence = xg_table[best_defence]
    
    logo_top_attack = "-"
    logo_best_defence = "-"
    if top_attack['logo']:
        logo_top_attack = top_attack['logo']
    if best_defence['logo']:
        logo_best_defence = best_defence['logo']
    
    team_with_top_attack = {
        'team_name': top_attack['team_name'],
        'logo': logo_top_attack,
    }
    team_with_best_defence = {
        'team_name': best_defence['team_name'],
        'logo': logo_best_defence,
    }

    # Return summary (Indonesian: Kembalikan ringkasan)
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
