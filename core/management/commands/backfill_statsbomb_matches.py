"""Management command to backfill missing Match rows from StatsBomb data."""

import csv
import json
import re
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models.competition import Competition
from core.models.match import Match
from core.models.season import Season
from core.models.team import Team


def normalize(name):
    return (name or "").strip().lower()


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[\s._]+", "-", text)
    return re.sub(r"[^a-z0-9-]+", "", text)


def load_team_map(team_map_path):
    path = Path(team_map_path)
    if not team_map_path or not path.exists():
        return {}

    team_map = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sb_name = (row.get("statsbomb_name") or "").strip()
            csv_name = (row.get("csv_name") or "").strip()
            if sb_name and csv_name:
                team_map[normalize(sb_name)] = csv_name
    return team_map


def load_matches(matches_path):
    path = Path(matches_path)
    if not path.exists():
        return None, f"matches.json not found: {matches_path}"
    if path.stat().st_size == 0:
        return None, f"matches.json is empty: {matches_path}"

    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError:
        return None, f"matches.json is not valid JSON: {matches_path}"

    if not isinstance(payload, list):
        return None, f"matches.json does not contain a list: {matches_path}"
    return payload, None


class Command(BaseCommand):
    help = "Create missing Match rows from StatsBomb matches.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--matches-json",
            default="",
            help="Path to StatsBomb matches.json",
        )
        parser.add_argument(
            "--team-map",
            default="",
            help="CSV map with headers `statsbomb_name,csv_name`",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without writing to the DB",
        )

    def handle(self, *args, **options):
        team_map_path = options["team_map"] or settings.STATSBOMB_DATA_DIR / "shots" / "team_map.csv"
        matches_path = options["matches_json"] or settings.STATSBOMB_DATA_DIR / "shots" / "matches.json"

        team_map = load_team_map(team_map_path)
        sb_matches, error = load_matches(matches_path)
        if error:
            self.stderr.write(self.style.ERROR(error))
            return

        created = 0
        skipped = 0

        for item in sb_matches:
            match_id = item.get("match_id")
            match_date = item.get("match_date")
            home = (item.get("home_team") or {}).get("home_team_name")
            away = (item.get("away_team") or {}).get("away_team_name")
            competition_name = (item.get("competition") or {}).get("competition_name")
            season_name = (item.get("season") or {}).get("season_name")

            if not (match_id and match_date and home and away and competition_name and season_name):
                skipped += 1
                continue

            if Match.objects.filter(match_id=str(match_id)).exists():
                skipped += 1
                continue

            try:
                date_obj = datetime.strptime(match_date, "%Y-%m-%d")
            except ValueError:
                skipped += 1
                continue

            home_name = team_map.get(normalize(home), home)
            away_name = team_map.get(normalize(away), away)

            competition, _ = Competition.objects.get_or_create(name=competition_name)
            season, _ = Season.objects.get_or_create(
                competition=competition,
                name=season_name,
                slug=slugify(season_name),
            )
            home_team, _ = Team.objects.get_or_create(name=home_name)
            away_team, _ = Team.objects.get_or_create(name=away_name)

            if options["dry_run"]:
                self.stdout.write(
                    f"[DRY RUN] {match_id} {home_name} vs {away_name} ({season_name})"
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

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: {created} would be created, {skipped} skipped.")
            )
            return

        self.stdout.write(self.style.SUCCESS(f"Done: {created} created, {skipped} skipped."))
