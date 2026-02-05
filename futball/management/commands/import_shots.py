import csv
import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand

from futball.models import Match, Shot, Team


OUTCOME_MAP = {
    "Goal": "goal",
    "Saved": "saved",
    "Saved Off Target": "saved",
    "Blocked": "blocked",
    "Off T": "off_target",
    "Off Target": "off_target",
    "Wayward": "off_target",
    "Post": "off_target",
}

BODY_PART_MAP = {
    "Right Foot": "right_foot",
    "Left Foot": "left_foot",
    "Head": "head",
}

SHOT_TYPE_MAP = {
    "Open Play": "open_play",
    "Penalty": "penalty",
    "Free Kick": "free_kick",
}


class Command(BaseCommand):
    help = "Import StatsBomb shot-by-shot events from JSON files"

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            type=str,
            help="File or directory containing StatsBomb event JSON files",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete existing shots for a match before importing",
        )
        parser.add_argument(
            "--match-map",
            type=str,
            default="",
            help=(
                "CSV map for match ids with headers "
                "`statsbomb_match_id,match_id`"
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report counts without writing to the DB",
        )

    def handle(self, *args, **options):
        input_path = Path(options["path"])
        replace = options["replace"]
        dry_run = options["dry_run"]
        match_map = self.load_match_map(options["match_map"])

        if not input_path.exists():
            self.stderr.write(
                self.style.ERROR(f"Path not found: {input_path}")
            )
            return

        files = self.collect_files(input_path)
        if not files:
            self.stderr.write(
                self.style.ERROR("No JSON files found.")
            )
            return

        total_created = total_skipped = total_events = 0

        for file_path in files:
            created, skipped, events = self.import_file(
                file_path=file_path,
                replace=replace,
                dry_run=dry_run,
                match_map=match_map,
            )
            total_created += created
            total_skipped += skipped
            total_events += events

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: {total_events} shots scanned, "
                    f"{total_created} would be created, "
                    f"{total_skipped} skipped."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {total_events} shots scanned, "
                f"{total_created} created, "
                f"{total_skipped} skipped."
            )
        )

    # --------------------
    # Helpers
    # --------------------

    @staticmethod
    def collect_files(input_path: Path):
        if input_path.is_file():
            return [input_path] if input_path.suffix == ".json" else []

        files = sorted(input_path.rglob("*.json"))
        return [
            f for f in files
            if f.name not in {"matches.json", "competitions.json"}
        ]

    @staticmethod
    def load_match_map(path):
        if not path:
            return {}

        match_map = {}
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sb_id = str(row.get("statsbomb_match_id", "")).strip()
                match_id = str(row.get("match_id", "")).strip()
                if sb_id and match_id:
                    match_map[sb_id] = match_id
        return match_map

    def import_file(self, file_path, replace, dry_run, match_map):
        statsbomb_id = file_path.stem
        match_id = match_map.get(statsbomb_id, statsbomb_id)

        match = Match.objects.filter(match_id=match_id).first()
        if not match:
            self.stdout.write(
                self.style.WARNING(
                    f"Skip {file_path.name}: no Match with match_id={match_id}"
                )
            )
            return 0, 0, 0

        if replace and not dry_run:
            Shot.objects.filter(match=match).delete()

        with open(file_path, encoding="utf-8") as f:
            events = json.load(f)

        if not isinstance(events, list):
            self.stdout.write(
                self.style.WARNING(
                    f"Skip {file_path.name}: JSON is not a list of events"
                )
            )
            return 0, 0, 0

        to_create = []
        skipped = 0

        for event in events:
            if (event.get("type") or {}).get("name") != "Shot":
                continue

            shot_payload = event.get("shot") or {}
            location = event.get("location") or []
            if len(location) < 2:
                skipped += 1
                continue

            x = float(location[0])
            y = float(location[1])

            team_name = (event.get("team") or {}).get("name", "")
            team = self.resolve_team(match, team_name)

            outcome_name = (shot_payload.get("outcome") or {}).get("name", "")
            outcome = OUTCOME_MAP.get(outcome_name, "off_target")

            body_part_name = (shot_payload.get("body_part") or {}).get("name", "")
            body_part = BODY_PART_MAP.get(body_part_name, "")

            shot_type_name = (shot_payload.get("type") or {}).get("name", "")
            shot_type = SHOT_TYPE_MAP.get(shot_type_name, "")

            xg = shot_payload.get("statsbomb_xg") or 0.0

            to_create.append(
                Shot(
                    match=match,
                    team=team,
                    minute=int(event.get("minute") or 0),
                    second=int(event.get("second") or 0),
                    x=x,
                    y=y,
                    xg=float(xg),
                    outcome=outcome,
                    is_goal=(outcome_name == "Goal"),
                    body_part=body_part,
                    shot_type=shot_type,
                )
            )

        if dry_run:
            return len(to_create), skipped, len(to_create) + skipped

        Shot.objects.bulk_create(to_create)

        self.stdout.write(
            self.style.SUCCESS(
                f"{file_path.name}: {len(to_create)} created, {skipped} skipped"
            )
        )
        return len(to_create), skipped, len(to_create) + skipped

    @staticmethod
    def resolve_team(match, team_name):
        if not team_name:
            return match.home_team

        if match.home_team.name.lower() == team_name.lower():
            return match.home_team
        if match.away_team.name.lower() == team_name.lower():
            return match.away_team

        team, _ = Team.objects.get_or_create(name=team_name)
        return team
