from django.core.management.base import BaseCommand
from django.db import transaction

from futball.models import Competition, Season


DEFAULT_MAP = {
    "English Premier League (football)": "Premier League",
    "English Premier League": "Premier League",
    "German Bundesliga (football)": "Bundesliga",
    "German Bundesliga": "Bundesliga",
    "1. Bundesliga": "Bundesliga",
    "Spanish La Liga (football)": "La Liga",
    "Spanish La Liga": "La Liga",
    "French Ligue 1 (football)": "Ligue 1",
    "French Ligue 1": "Ligue 1",
    "Italian Serie A (football)": "Serie A",
    "Italian Serie A": "Serie A",
}


class Command(BaseCommand):
    help = "Merge duplicate competitions into short-name versions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without writing to the DB",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        merged = 0
        skipped = 0

        for source_name, target_name in DEFAULT_MAP.items():
            source = Competition.objects.filter(name=source_name).first()
            if not source:
                skipped += 1
                continue

            target = Competition.objects.filter(name=target_name).first()
            if not target:
                if dry_run:
                    self.stdout.write(
                        f"[DRY RUN] Would create Competition: {target_name}"
                    )
                    # keep as None in dry-run
                else:
                    target = Competition.objects.create(
                        name=target_name,
                        country=source.country,
                    )

            if target and source.id == target.id:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] Would merge '{source_name}' -> '{target_name}'"
                )
                merged += 1
                continue

            with transaction.atomic():
                Season.objects.filter(competition=source).update(competition=target)
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
