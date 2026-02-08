import json
import os
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Copy StatsBomb event JSON files into data/shots so import_shots can run"

    def add_arguments(self, parser):
        parser.add_argument(
            "--open-data-root",
            required=True,
            help="Path to the StatsBomb open-data repository root",
        )
        parser.add_argument(
            "--matches-json",
            default="data/shots/matches.json",
            help="Path to merged matches.json (default: data/shots/matches.json)",
        )
        parser.add_argument(
            "--out-dir",
            default="data/shots/events",
            help="Destination directory for event JSON files",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip copying if event file already exists",
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
        open_data_root = Path(options["open_data_root"])
        matches_json = Path(options["matches_json"])
        out_dir = Path(options["out_dir"])
        skip_existing = options["skip_existing"]
        limit = options["limit"]
        dry_run = options["dry_run"]

        if not open_data_root.exists():
            self.stderr.write(
                self.style.ERROR(f"open-data root not found: {open_data_root}")
            )
            return

        if not matches_json.exists():
            self.stderr.write(
                self.style.ERROR(f"matches.json not found: {matches_json}")
            )
            return
        if matches_json.stat().st_size == 0:
            self.stderr.write(
                self.style.ERROR(f"matches.json is empty: {matches_json}")
            )
            return

        events_root = open_data_root / "data" / "events"
        if not events_root.exists():
            self.stderr.write(
                self.style.ERROR(f"events directory not found: {events_root}")
            )
            return

        try:
            with open(matches_json, encoding="utf-8") as f:
                matches = json.load(f)
        except json.JSONDecodeError:
            self.stderr.write(
                self.style.ERROR(f"matches.json is not valid JSON: {matches_json}")
            )
            return
        if not isinstance(matches, list):
            self.stderr.write(
                self.style.ERROR(f"matches.json does not contain a list: {matches_json}")
            )
            return

        match_ids = []
        for m in matches:
            mid = m.get("match_id")
            if mid is not None:
                match_ids.append(str(mid))

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
                continue

            if skip_existing and dst.exists():
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
