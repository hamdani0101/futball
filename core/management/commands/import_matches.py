from email.policy import default
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models.competition import Competition
from core.models.season import Season
from core.models.match import Match
from core.models.match_team_stat import MatchTeamStats
from core.models.team import Team
from core.models.stadium import Stadium


class Command(BaseCommand):
    help = "Import matches from StatsBomb directory (data/matches)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-dir",
            type=str,
            required=True,
            help="Path to data/matches directory",
        )

    # =====================
    # ENTRY
    # =====================

    def handle(self, *args, **options):
        base_dir = Path(options["base_dir"])

        total_created = total_updated = total_skipped = 0

        for comp_dir in base_dir.iterdir():
            if not comp_dir.is_dir():
                continue

            for season_file in comp_dir.glob("*.json"):
                self.stdout.write(f"Processing {season_file}")

                created, updated, skipped = self.import_file(season_file)

                total_created += created
                total_updated += updated
                total_skipped += skipped

        self.stdout.write(
            self.style.SUCCESS(
                f"\nTOTAL → created={total_created}, updated={total_updated}, skipped={total_skipped}"
            )
        )

    # =====================
    # IMPORT FILE
    # =====================

    @transaction.atomic
    def import_file(self, path: Path):
        with open(path, encoding="utf-8") as f:
            matches = json.load(f)

        team_cache: Dict[str, Team] = {}
        stadium_cache: Dict[str, Stadium] = {}

        created = updated = skipped = 0

        for m in matches:
            try:
                match, is_created = self.process_match(
                    m, team_cache, stadium_cache
                )

                if match:
                    if is_created:
                        created += 1
                    else:
                        updated += 1
                else:
                    skipped += 1

            except Exception as e:
                skipped += 1
                self.stderr.write(f"Error: {e}")

        return created, updated, skipped

    # =====================
    # PROCESS MATCH
    # =====================

    def process_match(self, m: Dict[str, Any], team_cache, stadium_cache):
        match_id = str(m.get("match_id"))

        home_name = (m.get("home_team") or {}).get("home_team_name")
        away_name = (m.get("away_team") or {}).get("away_team_name")
        
        home_id = m.get("home_team", {}).get("home_team_id")
        away_id = m.get("away_team", {}).get("away_team_id")

        if not (match_id and home_name and away_name):
            return None, False

        # --------------------
        # DATETIME
        # --------------------
        match_date = self.parse_datetime(
            m.get("match_date"),
            m.get("kick_off"),
        )

        # --------------------
        # STATUS
        # --------------------
        status = self.map_status(m.get("match_status"))

        # --------------------
        # SEASON + COMPETITION
        # --------------------
        competition_name = (m.get("competition") or {}).get("competition_name")
        season_name = (m.get("season") or {}).get("season_name")

        season = self.get_or_create_season(competition_name, season_name)

        # --------------------
        # STADIUM (NEW)
        # --------------------
        stadium = self.get_stadium(
            m.get("stadium"),
            m.get("stadium_country"),
            stadium_cache,
        )
        
        # --------------------
        # TEAMS
        # --------------------
        home_team = self.get_team(home_name, home_id, None, team_cache)
        away_team = self.get_team(away_name, away_id, None, team_cache)


        # --------------------
        # MATCH UPSERT
        # --------------------
        match, created = Match.objects.update_or_create(
            external_id=match_id,
            defaults={
                "season": season,
                "home_team": home_team,
                "away_team": away_team,
                "match_date": match_date,
                "match_week": m.get("match_week"),
                "stage": m.get("competition_stage"),
                "status": status,
                "stadium": stadium,
            },
        )

        if not created:
            match.season = season
            match.home_team = home_team
            match.away_team = away_team
            match.match_date = match_date
            match.match_week = m.get("match_week")
            match.stage = m.get("competition_stage")
            match.status = status
            match.stadium = stadium
            match.save()

        # --------------------
        # SCORE → STATS
        # --------------------
        self.upsert_stats(
            match,
            home_team,
            goals=m.get("home_score") or 0,
        )

        self.upsert_stats(
            match,
            away_team,
            goals=m.get("away_score") or 0,
        )

        return match, created

    # =====================
    # HELPERS
    # =====================

    def get_team(self, name: str, external_id: int, stadium: Stadium | None, cache: Dict[str, Team]) -> Team:
        key = external_id

        if key not in cache:
            cache[key], _ = Team.objects.update_or_create(
                external_id=external_id,
                defaults={
                    "name": name.strip(),
                    "home_stadium": stadium,
                },
            )
        return cache[key]

    def get_stadium(self, stadium_data, country, cache):
        if not stadium_data:
            return None

        stadium_id = stadium_data.get("id")
        name = stadium_data.get("name")

        if not name:
            return None

        key = stadium_id or name.lower()

        if key not in cache:
            stadium, _ = Stadium.objects.get_or_create(
                external_id=stadium_id,
                defaults={
                    "name": name,
                    "country": country,
                },
            )

            # fallback kalau external_id kosong
            if stadium_id:
                stadium, _ = Stadium.objects.get_or_create(
                    external_id=stadium_id,
                    defaults={
                        "name": name,
                        "country": country,
                    },
                )
            else:
                stadium, _ = Stadium.objects.get_or_create(
                    name=name,
                    defaults={"country": country},
                )

            cache[key] = stadium

        return cache[key]

    def get_or_create_season(self, competition_name, season_name):
        competition, _ = Competition.objects.get_or_create(
            name=competition_name
        )
        season, _ = Season.objects.get_or_create(
            competition=competition,
            name=season_name,
        )
        return season

    def parse_datetime(self, date_str, time_str=None):
        if time_str:
            try:
                return datetime.fromisoformat(f"{date_str}T{time_str}")
            except Exception:
                pass
        return datetime.strptime(date_str, "%Y-%m-%d")

    def map_status(self, status):
        return {
            "available": "finished",
            "scheduled": "scheduled",
            "deleted": "cancelled",
        }.get(status, "finished")

    def upsert_stats(self, match, team, goals=0):
        MatchTeamStats.objects.update_or_create(
            match=match,
            team=team,
            defaults={
                "goals": goals,
                "xg": 0.0,
                "shots": 0,
                "shots_on_target": 0,
            },
        )