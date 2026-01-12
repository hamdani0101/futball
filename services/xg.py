from collections import defaultdict
from analysis.models import Match


def build_xg_table(season):
    table = defaultdict(lambda: {
        "xgf": 0.0,
        "xga": 0.0,
        "gf": 0,
        "ga": 0,
        "matches": 0,
    })

    matches = Match.objects.filter(season=season)

    for m in matches:
        home = m.home_team.name
        away = m.away_team.name

        # ambil stats dari CSV (pastikan field ada)
        hs = getattr(m, "home_shots", 0)
        hst = getattr(m, "home_shots_on_target", 0)
        as_ = getattr(m, "away_shots", 0)
        ast = getattr(m, "away_shots_on_target", 0)

        home_xg = hst * 0.30 + (hs - hst) * 0.08
        away_xg = ast * 0.30 + (as_ - ast) * 0.08

        table[home]["xgf"] += home_xg
        table[home]["xga"] += away_xg
        table[home]["gf"] += m.home_score
        table[home]["ga"] += m.away_score
        table[home]["matches"] += 1

        table[away]["xgf"] += away_xg
        table[away]["xga"] += home_xg
        table[away]["gf"] += m.away_score
        table[away]["ga"] += m.home_score
        table[away]["matches"] += 1

    return table
