"""Management command to fetch statsbomb events."""

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from futball.models.match import Match


class Command(BaseCommand):
    help = "Copy StatsBomb event JSON files into data/shots/events"

    def add_arguments(self, parser):
        parser.add_argument(
            "--open-data-root",
            default="",
            help=(
                "Path to the StatsBomb open-data repository root or its data "
                "directory. Defaults to STATSBOMB_DATA_DIR."
            ),
        )
        parser.add_argument(
            "--out-dir",
            default="",
            help="Destination directory for event JSON files",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit number of matches to copy (default: 0 = all)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be copied without writing files",
        )

    def handle(self, *args, **options):
        open_data_root = Path(options["open_data_root"] or settings.STATSBOMB_DATA_DIR)
        out_dir = Path(options["out_dir"] or settings.STATSBOMB_DATA_DIR / "shots" / "events")
        limit = options["limit"]
        dry_run = options["dry_run"]

        if not open_data_root.exists():
            self.stderr.write(
                self.style.ERROR(f"open-data root not found: {open_data_root}")
            )
            return

        events_root = self.resolve_events_root(open_data_root)
        if not events_root.exists():
            self.stderr.write(
                self.style.ERROR(f"events directory not found: {events_root}")
            )
            return

        match_ids = list(
            Match.objects.order_by("match_id").values_list("match_id", flat=True)
        )

        if limit and limit > 0:
            match_ids = match_ids[:limit]

        if not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)

        copied = 0
        skipped = 0
        missing = 0

        for match_id in match_ids:
            src = events_root / f"{match_id}.json"
            dst = out_dir / f"{match_id}.json"

            if not src.exists():
                missing += 1
                self.stdout.write(
                    self.style.WARNING(f"Missing event file for match {match_id}: {src}")
                )
                continue

            if dst.exists():
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(f"Skip existing event file for match {match_id}: {dst}")
                )
                continue

            if src.resolve() == dst.resolve():
                skipped += 1
                continue

            if dry_run:
                copied += 1
                continue

            shutil.copy2(src, dst)
            copied += 1

        prefix = "DRY RUN: " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Copied {copied}, skipped {skipped}, missing {missing}"
            )
        )

    @staticmethod
    def resolve_events_root(open_data_root: Path):
        direct_events = open_data_root / "events"
        if direct_events.exists():
            return direct_events

        if open_data_root.name == "data":
            return open_data_root / "events"

        return open_data_root / "data" / "events"
