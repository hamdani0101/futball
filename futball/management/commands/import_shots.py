"""Management command to import shots."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from futball.models.match import Match
from futball.models.player import Player
from futball.models.shots import Shot


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
            nargs="?",
            type=str,
            default="",
            help=(
                "File or directory containing StatsBomb event JSON files. "
                "Defaults to STATSBOMB_DATA_DIR/shots/events."
            ),
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete existing shots for a match before importing",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report counts without writing to the DB",
        )

    def handle(self, *args, **options):
        input_path = Path(options["path"] or settings.STATSBOMB_DATA_DIR / "shots" / "events")
        replace = options["replace"]
        dry_run = options["dry_run"]

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

    def import_file(self, file_path, replace, dry_run):
        statsbomb_id = file_path.stem
        match = Match.objects.filter(match_id=statsbomb_id).first()
        if not match:
            self.stdout.write(
                self.style.WARNING(
                    f"Skip {file_path.name}: no Match with match_id={statsbomb_id}"
                )
            )
            return 0, 0, 0

        with open(file_path, encoding="utf-8") as f:
            events = json.load(f)

        if not isinstance(events, list):
            self.stdout.write(
                self.style.WARNING(
                    f"Skip {file_path.name}: JSON is not a list of events"
                )
            )
            return 0, 0, 0

        shot_records = []
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
            if not (0 <= x <= 120 and 0 <= y <= 80):
                skipped += 1
                continue

            team_name = (event.get("team") or {}).get("name", "")
            team = self.resolve_team(match, team_name)
            if not team:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skip shot {event.get('id', 'unknown')} in {file_path.name}: "
                        f"team mismatch '{team_name}'"
                    )
                )
                skipped += 1
                continue

            player_payload = event.get("player") or {}
            player = None
            player_id = player_payload.get("id")
            player_name = player_payload.get("name")
            if player_id is not None:
                player, created = Player.objects.get_or_create(
                    external_id=player_id,
                    defaults={
                        "name": player_name or "Unknown",
                        "team_now": team,
                    },
                )
                updates = []
                if not created and player_name and player.name != player_name:
                    player.name = player_name
                    updates.append("name")
                if player.team_now_id != team.id:
                    player.team_now = team
                    updates.append("team_now")
                if updates:
                    player.save(update_fields=updates)

            outcome_name = (shot_payload.get("outcome") or {}).get("name", "")
            outcome = OUTCOME_MAP.get(outcome_name, "off_target")

            body_part_name = (shot_payload.get("body_part") or {}).get("name", "")
            body_part = BODY_PART_MAP.get(body_part_name, "")

            shot_type_name = (shot_payload.get("type") or {}).get("name", "")
            shot_type = SHOT_TYPE_MAP.get(shot_type_name, "")

            xg = shot_payload.get("statsbomb_xg")
            try:
                xg = float(xg) if xg is not None else 0.0
            except (TypeError, ValueError):
                xg = 0.0

            event_id = str(event.get("id") or "").strip()
            if not event_id:
                skipped += 1
                continue

            shot_records.append(
                {
                    "external_event_id": event_id,
                    "match": match,
                    "team": team,
                    "minute": int(event.get("minute") or 0),
                    "second": int(event.get("second") or 0),
                    "x": x,
                    "y": y,
                    "xg": float(xg),
                    "outcome": outcome,
                    "is_goal": outcome_name == "Goal",
                    "body_part": body_part,
                    "shot_type": shot_type,
                    "player": player,
                }
            )

        if dry_run:
            return len(shot_records), skipped, len(shot_records) + skipped

        shot_event_ids = [record["external_event_id"] for record in shot_records]

        if replace:
            Shot.objects.filter(match=match).delete()
        else:
            Shot.objects.filter(match=match, external_event_id__isnull=True).delete()
            if shot_event_ids:
                Shot.objects.filter(match=match).exclude(
                    external_event_id__in=shot_event_ids
                ).delete()

        created_or_updated = 0
        for record in shot_records:
            event_id = record.pop("external_event_id")
            Shot.objects.update_or_create(
                external_event_id=event_id,
                defaults=record,
            )
            created_or_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{file_path.name}: {created_or_updated} imported, {skipped} skipped"
            )
        )
        return created_or_updated, skipped, len(shot_records) + skipped

    @staticmethod
    def resolve_team(match, team_name):
        if not team_name:
            return match.home_team

        team_name = team_name.lower()
        home = match.home_team.name.lower()
        away = match.away_team.name.lower()

        if team_name in home or home in team_name:
            return match.home_team
        if team_name in away or away in team_name:
            return match.away_team

        return None
