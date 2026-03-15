"""Management command to import StatsBomb pass events from JSON files."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import Pass, Player
from core.models.match import Match


OUTCOME_MAP = {
    "Incomplete": Pass.Outcome.INCOMPLETE,
    "Out": Pass.Outcome.OUT,
    "Pass Offside": Pass.Outcome.OFFSIDE,
}

HEIGHT_MAP = {
    "Ground Pass": Pass.Height.GROUND,
    "Low Pass": Pass.Height.LOW,
    "High Pass": Pass.Height.HIGH,
}

BODY_PART_MAP = {
    "Right Foot": Pass.BodyPart.RIGHT_FOOT,
    "Left Foot": Pass.BodyPart.LEFT_FOOT,
    "Head": Pass.BodyPart.HEAD,
    "Chest": Pass.BodyPart.CHEST,
}

TECHNIQUE_MAP = {
    "Backheel": Pass.Technique.BACKHEEL,
    "Half Volley": Pass.Technique.HALF_VOLLEY,
    "Lob": Pass.Technique.LOB,
    "Normal": Pass.Technique.NORMAL,
    "Overhead Kick": Pass.Technique.OVERHEAD,
    "Volley": Pass.Technique.VOLLEY,
}

PASS_TYPE_MAP = {
    "Corner": Pass.PassType.CORNER,
    "Free Kick": Pass.PassType.FREE_KICK,
    "Goal Kick": Pass.PassType.GOAL_KICK,
    "Kick Off": Pass.PassType.KICK_OFF,
    "Open Play": Pass.PassType.OPEN_PLAY,
    "Recovery": Pass.PassType.RECOVERY,
    "Throw-in": Pass.PassType.THROW_IN,
}


class Command(BaseCommand):
    help = "Import StatsBomb pass events from JSON files"

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
            help="Delete existing passes for a match before importing",
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
            self.stderr.write(self.style.ERROR(f"Path not found: {input_path}"))
            return

        files = self.collect_files(input_path)
        if not files:
            self.stderr.write(self.style.ERROR("No JSON files found."))
            return

        total_imported = total_skipped = total_events = 0

        for file_path in files:
            imported, skipped, events = self.import_file(
                file_path=file_path,
                replace=replace,
                dry_run=dry_run,
            )
            total_imported += imported
            total_skipped += skipped
            total_events += events

        prefix = "DRY RUN: " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}{total_events} pass events scanned, "
                f"{total_imported} imported, {total_skipped} skipped."
            )
        )

    @staticmethod
    def collect_files(input_path: Path):
        if input_path.is_file():
            return [input_path] if input_path.suffix == ".json" else []

        files = sorted(input_path.rglob("*.json"))
        return [
            file_path
            for file_path in files
            if file_path.name not in {"matches.json", "competitions.json"}
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

        with open(file_path, encoding="utf-8") as handle:
            events = json.load(handle)

        if not isinstance(events, list):
            self.stdout.write(
                self.style.WARNING(
                    f"Skip {file_path.name}: JSON is not a list of events"
                )
            )
            return 0, 0, 0

        pass_records = []
        skipped = 0

        for event in events:
            if (event.get("type") or {}).get("name") != "Pass":
                continue

            pass_payload = event.get("pass") or {}
            location = event.get("location") or []
            end_location = pass_payload.get("end_location") or []

            if len(location) < 2 or len(end_location) < 2:
                skipped += 1
                continue

            team = self.resolve_team(
                match=match,
                team_name=(event.get("team") or {}).get("name", ""),
            )
            if not team:
                skipped += 1
                continue

            player = self.resolve_player(event.get("player") or {}, team)
            recipient = self.resolve_player(pass_payload.get("recipient") or {}, team)

            event_id = str(event.get("id") or "").strip()
            if not event_id:
                skipped += 1
                continue

            pass_records.append(
                {
                    "external_event_id": event_id,
                    "event_index": int(event.get("index") or 0),
                    "period": int(event.get("period") or 1),
                    "possession": int(event.get("possession") or 0),
                    "match": match,
                    "team": team,
                    "player": player,
                    "recipient": recipient,
                    "minute": int(event.get("minute") or 0),
                    "second": int(event.get("second") or 0),
                    "x": float(location[0]),
                    "y": float(location[1]),
                    "end_x": float(end_location[0]),
                    "end_y": float(end_location[1]),
                    "length": self.to_float(pass_payload.get("length")),
                    "angle": self.to_float(pass_payload.get("angle")),
                    "outcome": self.map_outcome(pass_payload),
                    "height": self.map_height(pass_payload),
                    "body_part": self.map_body_part(pass_payload),
                    "technique": self.map_technique(pass_payload),
                    "pass_type": self.map_pass_type(pass_payload),
                    "play_pattern": (event.get("play_pattern") or {}).get("name", ""),
                    "assisted_shot_event_id": str(pass_payload.get("assisted_shot_id") or "").strip(),
                    "under_pressure": bool(event.get("under_pressure", False)),
                    "is_cross": bool(pass_payload.get("cross", False)),
                    "is_cut_back": bool(pass_payload.get("cut_back", False)),
                    "is_switch": bool(pass_payload.get("switch", False)),
                    "is_through_ball": bool(pass_payload.get("through_ball", False)),
                    "shot_assist": bool(pass_payload.get("shot_assist", False)),
                    "goal_assist": bool(pass_payload.get("goal_assist", False)),
                }
            )

        if dry_run:
            return len(pass_records), skipped, len(pass_records) + skipped

        event_ids = [record["external_event_id"] for record in pass_records]

        if replace:
            Pass.objects.filter(match=match).delete()
        elif event_ids:
            Pass.objects.filter(match=match).exclude(
                external_event_id__in=event_ids
            ).delete()

        imported = 0
        for record in pass_records:
            event_id = record.pop("external_event_id")
            Pass.objects.update_or_create(
                external_event_id=event_id,
                defaults=record,
            )
            imported += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{file_path.name}: {imported} imported, {skipped} skipped"
            )
        )
        return imported, skipped, len(pass_records) + skipped

    def resolve_player(self, payload, team):
        player_id = payload.get("id")
        player_name = payload.get("name")
        if player_id is None:
            return None

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
        return player

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

    @staticmethod
    def to_float(value):
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def map_outcome(pass_payload):
        outcome_name = (pass_payload.get("outcome") or {}).get("name")
        if not outcome_name:
            return Pass.Outcome.COMPLETE
        return OUTCOME_MAP.get(outcome_name, Pass.Outcome.UNKNOWN)

    @staticmethod
    def map_height(pass_payload):
        height_name = (pass_payload.get("height") or {}).get("name")
        return HEIGHT_MAP.get(height_name, Pass.Height.UNKNOWN)

    @staticmethod
    def map_body_part(pass_payload):
        body_part_name = (pass_payload.get("body_part") or {}).get("name")
        return BODY_PART_MAP.get(body_part_name, Pass.BodyPart.OTHER if body_part_name else "")

    @staticmethod
    def map_technique(pass_payload):
        technique_name = (pass_payload.get("technique") or {}).get("name")
        if not technique_name:
            return ""
        return TECHNIQUE_MAP.get(technique_name, Pass.Technique.UNKNOWN)

    @staticmethod
    def map_pass_type(pass_payload):
        pass_type_name = (pass_payload.get("type") or {}).get("name")
        if not pass_type_name:
            return Pass.PassType.OPEN_PLAY
        return PASS_TYPE_MAP.get(pass_type_name, Pass.PassType.UNKNOWN)
