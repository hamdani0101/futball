import csv
import os

from django.core.management.base import BaseCommand
from django.db import transaction

from futball.models import Match, Shot, Team


class Command(BaseCommand):
    help = "Merge Team records using a team_map.csv (statsbomb_name -> csv_name)"

    def add_arguments(self, parser):
        parser.add_argument(
            "team_map_csv",
            nargs="?",
            default="data/shots/team_map.csv",
            help="Path to team_map.csv (default: data/shots/team_map.csv)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without writing to the DB",
        )

    def handle(self, *args, **options):
        path = options["team_map_csv"]
        dry_run = options["dry_run"]

        if not os.path.exists(path):
            self.stderr.write(self.style.ERROR(f"File not found: {path}"))
            return

        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sb_name = (row.get("statsbomb_name") or "").strip()
                csv_name = (row.get("csv_name") or "").strip()
                if sb_name and csv_name and sb_name != csv_name:
                    rows.append((sb_name, csv_name))

        if not rows:
            self.stdout.write(self.style.WARNING("No rows to merge."))
            return

        merged = 0
        skipped = 0

        for sb_name, csv_name in rows:
            source = Team.objects.filter(name=sb_name).first()
            target = Team.objects.filter(name=csv_name).first()

            if not source:
                skipped += 1
                continue

            if not target:
                if dry_run:
                    self.stdout.write(
                        f"[DRY RUN] Would create Team: {csv_name}"
                    )
                else:
                    target = Team.objects.create(name=csv_name)

            if source.id == target.id:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] Would merge '{sb_name}' -> '{csv_name}'"
                )
                merged += 1
                continue

            with transaction.atomic():
                Match.objects.filter(home_team=source).update(home_team=target)
                Match.objects.filter(away_team=source).update(away_team=target)
                Shot.objects.filter(team=source).update(team=target)
                source.delete()

            merged += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: {merged} merges, {skipped} skipped."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {merged} merged, {skipped} skipped."
            )
        )
