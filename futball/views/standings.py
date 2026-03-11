"""Views for league-table and standings pages."""

import re

from django.shortcuts import render

from futball.services.standings import build_league_table
from futball.views.selection import get_competition_season_selection


def normalize_competition_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"\(.*?\)", "", name)   # hapus (football)
    name = re.sub(r"[^a-z\s]", "", name)  # hapus simbol
    return name.strip()


def season_start_year(season_name: str) -> int | None:
    # Support formats like 2024/25, 2024-2025, 2024, 2425.
    years = re.findall(r"\d{4}", season_name or "")
    if years:
        return int(years[0])

    compact = re.search(r"\b(\d{2})(\d{2})\b", season_name or "")
    if not compact:
        return None

    yy = int(compact.group(1))
    return 1900 + yy if yy >= 90 else 2000 + yy


# Easy place to adjust quotas per competition.
UEFA_RULES = {
    "epl": dict(cl=4, el=2, ecl=1, relegation=3),
    "laliga": dict(cl=4, el=2, ecl=1, relegation=3),
    "bundesliga": dict(cl=4, el=2, ecl=1, relegation=3),
    "seriea": dict(cl=4, el=2, ecl=1, relegation=3),
    "ligue1": dict(cl=3, el=1, ecl=1, relegation=3),
}

COMPETITION_ALIAS = {
    "premier league": "epl",
    "english premier league": "epl",
    "epl": "epl",
    "la liga": "laliga",
    "liga bbva": "laliga",
    "spanish la liga": "laliga",
    "bundesliga": "bundesliga",
    "german bundesliga": "bundesliga",
    "serie a": "seriea",
    "italian serie a": "seriea",
    "ligue 1": "ligue1",
    "french ligue 1": "ligue1",
    "french ligue": "ligue1",
}


def get_quota_rules(alias: str | None, season_name: str | None) -> dict:
    rules = UEFA_RULES.get(alias, dict(cl=0, el=0, ecl=0, relegation=3)).copy()

    # UEFA Conference League starts from 2021/22.
    start_year = season_start_year(season_name or "")
    if start_year is not None and start_year <= 2020:
        rules["ecl"] = 0

    return rules


def league_table_view(request):
    selection = get_competition_season_selection(request)
    competition = selection["selected_competition"]
    season = selection["selected_season"]
    alias = None
    if competition:
        alias = COMPETITION_ALIAS.get(normalize_competition_name(competition.name))

    rules = get_quota_rules(alias, season.name if season else None)
    champions_league_places = rules["cl"]
    europa_league_places = rules["el"]
    conference_league_places = rules["ecl"]
    relegation_places = rules["relegation"]

    ranked_table = [
        {
            "rank": idx,
            "team": team,
            **stats,
        }
        for idx, (team, stats) in enumerate(build_league_table(season), start=1)
    ]

    if ranked_table:
        relegation_cutoff = len(ranked_table) - relegation_places
        champions_league_cutoff = champions_league_places
        europa_league_cutoff = champions_league_places + europa_league_places
        conference_league_cutoff = (
            champions_league_places + europa_league_places + conference_league_places
        )
    else:
        relegation_cutoff = 0
        champions_league_cutoff = 0
        europa_league_cutoff = 0
        conference_league_cutoff = 0

    return render(
        request,
        "futball/league_table.html",
        {
            "competitions": selection["competitions"],
            "seasons": selection["seasons"],
            "season_json_data": selection["season_json_data"],
            "selected_competition": competition,
            "selected_season": season,
            "table": ranked_table,
            "relegation_cutoff": relegation_cutoff,
            "champions_league_cutoff": champions_league_cutoff,
            "europa_league_cutoff": europa_league_cutoff,
            "conference_league_cutoff": conference_league_cutoff,
            "conference_league_places": conference_league_places,
        },
    )
