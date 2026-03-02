"""Management command to backfill statsbomb matches."""

import csv
import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand

from futball.models.competition import Competition
from futball.models.match import Match
from futball.models.season import Season
from futball.models.team import Team


# Normalize team name (Indonesian: Normalisasi nama tim)
def normalize(name):
    return (name or "").strip().lower()


class Command(BaseCommand):
    # Create missing Match rows from StatsBomb matches.json (Indonesian: Membuat data pertandingan yang hilang dari matches.json)
    help = "Create missing Match rows from StatsBomb matches.json"

    # Add command line arguments (Indonesian: Menambahkan argumen baris perintah)
    def add_arguments(self, parser):
        # Path to StatsBomb matches.json (Indonesian: Path ke file matches.json)
        parser.add_argument(
            "--matches-json",
            default="data/shots/matches.json",
            help="Path to StatsBomb matches.json",
        )
        # CSV map with headers `statsbomb_name,csv_name` (Indonesian: CSV map dengan header `statsbomb_name,csv_name`)
        parser.add_argument(
            "--team-map",
            default="data/shots/team_map.csv",
            help="CSV map with headers `statsbomb_name,csv_name`",
        )
        # Report changes without writing to the DB (Indonesian: Melaporkan perubahan tanpa menulis ke DB)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without writing to the DB",
        )

    # Handle the command (Indonesian: Menangani perintah)
    def handle(self, *args, **options):
        matches_path = options["matches_json"]
        team_map_path = options["team_map"]
        dry_run = options["dry_run"]

        # Check if matches.json exists (Indonesian: Memeriksa apakah matches.json ada)
        if not os.path.exists(matches_path):
            self.stderr.write(self.style.ERROR(f"matches.json not found: {matches_path}"))
            return
        if os.path.getsize(matches_path) == 0:
            self.stderr.write(self.style.ERROR(f"matches.json is empty: {matches_path}"))
            return

        # Load team map (Indonesian: Memuat peta tim)
        team_map = {}
        if team_map_path and os.path.exists(team_map_path):
            with open(team_map_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sb = (row.get("statsbomb_name") or "").strip()
                    csv_name = (row.get("csv_name") or "").strip()
                    if sb and csv_name:
                        team_map[normalize(sb)] = csv_name

        # Load matches.json (Indonesian: Memuat matches.json)
        try:
            with open(matches_path, encoding="utf-8") as f:
                sb_matches = json.load(f)
        except json.JSONDecodeError:
            self.stderr.write(self.style.ERROR(f"matches.json is not valid JSON: {matches_path}"))
            return
        if not isinstance(sb_matches, list):
            self.stderr.write(self.style.ERROR(f"matches.json does not contain a list: {matches_path}"))
            return

        # Initialize counters (Indonesian: Inisialisasi penghitung)
        created = 0
        skipped = 0

        # Process each match (Indonesian: Memproses setiap pertandingan)
        for m in sb_matches:
            match_id = m.get("match_id")
            match_date = m.get("match_date")
            home = (m.get("home_team") or {}).get("home_team_name")
            away = (m.get("away_team") or {}).get("away_team_name")
            competition_name = (m.get("competition") or {}).get("competition_name")
            season_name = (m.get("season") or {}).get("season_name")

            # Check if all required fields are present (Indonesian: Memeriksa apakah semua field yang diperlukan ada)
            if not (match_id and match_date and home and away and competition_name and season_name):
                skipped += 1
                continue

            # Check if match already exists (Indonesian: Memeriksa apakah pertandingan sudah ada)
            if Match.objects.filter(match_id=str(match_id)).exists():
                skipped += 1
                continue

            # Map team names (Indonesian: Memetakan nama tim)
            home_mapped = team_map.get(normalize(home), home)
            away_mapped = team_map.get(normalize(away), away)

            # Get or create competition and season (Indonesian: Mendapatkan atau membuat kompetisi dan musim)
            competition, _ = Competition.objects.get_or_create(
                name=competition_name
            )
            season, _ = Season.objects.get_or_create(
                competition=competition,
                name=season_name,
            )
            home_team, _ = Team.objects.get_or_create(name=home_mapped)
            away_team, _ = Team.objects.get_or_create(name=away_mapped)

            # Parse match date (Indonesian: Mengurai tanggal pertandingan)
            try:
                date_obj = datetime.strptime(match_date, "%Y-%m-%d")
            except ValueError:
                skipped += 1
                continue

            # Dry run mode (Indonesian: Mode kering)
            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] {match_id} {home_mapped} vs {away_mapped} ({season_name})"
                )
                created += 1
                continue

            # Create match (Indonesian: Membuat data pertandingan)
            Match.objects.create(
                match_id=str(match_id),
                season=season,
                home_team=home_team,
                away_team=away_team,
                match_date=date_obj,
                status="finished",
            )
            created += 1

        # Summary (Indonesian: Ringkasan)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: {created} would be created, {skipped} skipped."
                )
            )
            return

        # Actual creation (Indonesian: Benar-benar membuat data)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created} created, {skipped} skipped."
            )
        )
