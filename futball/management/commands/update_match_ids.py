import csv
import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from futball.models import Match


def normalize(name):
    return (name or "").strip().lower()


class Command(BaseCommand):
    help = "Update Match.match_id to StatsBomb match_id using matches.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--matches-json",
            default="data/shots/matches.json",
            help="Path to StatsBomb matches.json",
        )
        parser.add_argument(
            "--team-map",
            default="",
            help="Optional CSV map with headers `statsbomb_name,csv_name`",
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
        if os.path.getsize(matches_path) == 0:
            self.stderr.write(self.style.ERROR(f"matches.json is empty: {matches_path}"))
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

        index = {}
        for m in sb_matches:
            match_id = str(m.get("match_id") or "").strip()
            match_date = m.get("match_date")
            home = (m.get("home_team") or {}).get("home_team_name")
            away = (m.get("away_team") or {}).get("away_team_name")
            if not (match_id and match_date and home and away):
                continue
            home = team_map.get(normalize(home), home)
            away = team_map.get(normalize(away), away)
            key = (match_date, normalize(home), normalize(away))
            index[key] = match_id

        updated = 0
        skipped = 0

        qs = Match.objects.select_related("home_team", "away_team")

        for match in qs.iterator():
            key = (
                match.match_date.strftime("%Y-%m-%d"),
                normalize(match.home_team.name),
                normalize(match.away_team.name),
            )
            sb_id = index.get(key)
            if not sb_id:
                skipped += 1
                continue

            if match.match_id == sb_id:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] {match.match_id} -> {sb_id}"
                )
                updated += 1
                continue

            try:
                with transaction.atomic():
                    match.match_id = sb_id
                    match.save(update_fields=["match_id"])
                updated += 1
            except Exception:
                skipped += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: {updated} updated, {skipped} skipped."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {updated} updated, {skipped} skipped."
            )
        )
