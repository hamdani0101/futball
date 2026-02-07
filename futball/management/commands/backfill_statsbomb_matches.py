import csv
import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand

from futball.models import Competition, Match, Season, Team


def normalize(name):
    return (name or "").strip().lower()


class Command(BaseCommand):
    help = "Create missing Match rows from StatsBomb matches.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--matches-json",
            default="data/shots/matches.json",
            help="Path to StatsBomb matches.json",
        )
        parser.add_argument(
            "--team-map",
            default="data/shots/team_map.csv",
            help="CSV map with headers `statsbomb_name,csv_name`",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without writing to the DB",
        )

    def handle(self, *args, **options):
        matches_path = options["matches_json"]
        team_map_path = options["team_map"]
        dry_run = options["dry_run"]

        if not os.path.exists(matches_path):
            self.stderr.write(self.style.ERROR(f"matches.json not found: {matches_path}"))
            return

        team_map = {}
        if team_map_path and os.path.exists(team_map_path):
            with open(team_map_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sb = (row.get("statsbomb_name") or "").strip()
                    csv_name = (row.get("csv_name") or "").strip()
                    if sb and csv_name:
                        team_map[normalize(sb)] = csv_name

        with open(matches_path, encoding="utf-8") as f:
            sb_matches = json.load(f)

        created = 0
        skipped = 0

        for m in sb_matches:
            match_id = m.get("match_id")
            match_date = m.get("match_date")
            home = (m.get("home_team") or {}).get("home_team_name")
            away = (m.get("away_team") or {}).get("away_team_name")
            competition_name = (m.get("competition") or {}).get("competition_name")
            season_name = (m.get("season") or {}).get("season_name")

            if not (match_id and match_date and home and away and competition_name and season_name):
                skipped += 1
                continue

            if Match.objects.filter(match_id=str(match_id)).exists():
                skipped += 1
                continue

            home_mapped = team_map.get(normalize(home), home)
            away_mapped = team_map.get(normalize(away), away)

            competition, _ = Competition.objects.get_or_create(
                name=competition_name
            )
            season, _ = Season.objects.get_or_create(
                competition=competition,
                name=season_name,
            )
            home_team, _ = Team.objects.get_or_create(name=home_mapped)
            away_team, _ = Team.objects.get_or_create(name=away_mapped)

            try:
                date_obj = datetime.strptime(match_date, "%Y-%m-%d")
            except ValueError:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] {match_id} {home_mapped} vs {away_mapped} ({season_name})"
                )
                created += 1
                continue

            Match.objects.create(
                match_id=str(match_id),
                season=season,
                home_team=home_team,
                away_team=away_team,
                match_date=date_obj,
                status="finished",
            )
            created += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: {created} would be created, {skipped} skipped."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created} created, {skipped} skipped."
            )
        )
