import csv
import json
import os

from django.core.management.base import BaseCommand

from futball.models import Match, Team


def normalize(name):
    return (name or "").strip().lower()


class Command(BaseCommand):
    help = "List StatsBomb matches that don't map to local Match records"

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
            "--limit",
            type=int,
            default=50,
            help="Max number of unmatched rows to print (default: 50)",
        )

    def handle(self, *args, **options):
        matches_path = options["matches_json"]
        team_map_path = options["team_map"]
        limit = options["limit"]

        if not os.path.exists(matches_path):
            self.stderr.write(
                self.style.ERROR(f"matches.json not found: {matches_path}")
            )
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

        missing = 0
        printed = 0

        for m in sb_matches:
            match_id = m.get("match_id")
            match_date = m.get("match_date")
            home = (m.get("home_team") or {}).get("home_team_name")
            away = (m.get("away_team") or {}).get("away_team_name")
            if not (match_id and match_date and home and away):
                continue

            home_mapped = team_map.get(normalize(home), home)
            away_mapped = team_map.get(normalize(away), away)

            existing = Match.objects.filter(match_id=str(match_id)).first()
            if existing:
                same_date = existing.match_date.strftime("%Y-%m-%d") == match_date
                same_home = existing.home_team.name == home_mapped
                same_away = existing.away_team.name == away_mapped
                if same_date and same_home and same_away:
                    continue
                missing += 1
                if printed < limit:
                    self.stdout.write(
                        f"{match_id} {match_date} | {home} -> {home_mapped} "
                        f"vs {away} -> {away_mapped} "
                        f"| DB has {existing.match_date} "
                        f"{existing.home_team.name} vs {existing.away_team.name}"
                    )
                    printed += 1
                continue

            exists = Match.objects.filter(
                match_date=match_date,
                home_team__name=home_mapped,
                away_team__name=away_mapped,
            ).exists()

            if exists:
                continue

            missing += 1
            if printed < limit:
                home_exists = Team.objects.filter(name=home_mapped).exists()
                away_exists = Team.objects.filter(name=away_mapped).exists()
                self.stdout.write(
                    f"{match_id} {match_date} | {home} -> {home_mapped} "
                    f"({'ok' if home_exists else 'missing'}) vs "
                    f"{away} -> {away_mapped} "
                    f"({'ok' if away_exists else 'missing'})"
                )
                printed += 1

        self.stdout.write(
            self.style.WARNING(
                f"Total unmatched: {missing} (showing {printed})"
            )
        )
