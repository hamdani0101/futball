"""Management command to derive player minutes from StatsBomb events."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from futball.models.match import Match
from futball.models.player import Player
from futball.models.player_match import PlayerMatch


class Command(BaseCommand):
    help = "Update PlayerMatch starters and minutes from StatsBomb events"

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            nargs="?",
            type=str,
            default="",
            help=(
                "File or directory containing StatsBomb event JSON files. "
                "Defaults to STATSBOMB_DATA_DIR/events."
            ),
        )

    def handle(self, *args, **options):
        input_path = Path(options["path"] or settings.STATSBOMB_DATA_DIR / "events")
        if not input_path.exists():
            self.stderr.write(self.style.ERROR(f"Path not found: {input_path}"))
            return

        files = self.collect_files(input_path)
        if not files:
            self.stderr.write(self.style.ERROR("No event JSON files found."))
            return

        processed = 0
        skipped = 0

        for file_path in files:
            if self.process_match(file_path):
                processed += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {processed} matches updated, {skipped} skipped."
            )
        )

    @staticmethod
    def collect_files(input_path: Path):
        if input_path.is_file():
            return [input_path] if input_path.suffix == ".json" else []

        files = sorted(input_path.rglob("*.json"))
        return [
            file_path for file_path in files
            if file_path.name not in {"matches.json", "competitions.json"}
        ]

    def process_match(self, file_path: Path):
        match = Match.objects.filter(match_id=file_path.stem).first()
        if not match:
            self.stdout.write(
                self.style.WARNING(
                    f"Skip {file_path.name}: no Match with match_id={file_path.stem}"
                )
            )
            return False

        with file_path.open(encoding="utf-8") as handle:
            events = json.load(handle)

        if not isinstance(events, list):
            self.stdout.write(
                self.style.WARNING(
                    f"Skip {file_path.name}: JSON is not a list of events"
                )
            )
            return False

        with transaction.atomic():
            PlayerMatch.objects.filter(match=match).update(
                is_starter=False,
                minute_on=0,
                minute_off=90,
            )

            for event in events:
                event_type = (event.get("type") or {}).get("name")
                if event_type == "Starting XI":
                    self.apply_starting_xi(match, event)
                elif event_type == "Substitution":
                    self.apply_substitution(match, event)

        self.stdout.write(self.style.SUCCESS(f"{file_path.name}: player minutes updated"))
        return True

    def apply_starting_xi(self, match, event):
        team = self.resolve_team(match, (event.get("team") or {}).get("name", ""))
        if not team:
            return

        lineup = ((event.get("tactics") or {}).get("lineup") or [])
        for item in lineup:
            player_payload = item.get("player") or {}
            player = self.get_or_create_player(player_payload, team)
            if not player:
                continue

            PlayerMatch.objects.update_or_create(
                player=player,
                match=match,
                defaults={
                    "team": team,
                    "is_starter": True,
                    "minute_on": 0,
                    "minute_off": 90,
                },
            )

    def apply_substitution(self, match, event):
        team = self.resolve_team(match, (event.get("team") or {}).get("name", ""))
        if not team:
            return

        minute = int(event.get("minute") or 0)

        outgoing = self.get_or_create_player(event.get("player") or {}, team)
        if outgoing:
            player_match, created = PlayerMatch.objects.get_or_create(
                player=outgoing,
                match=match,
                defaults={
                    "team": team,
                    "is_starter": False,
                    "minute_on": 0,
                    "minute_off": 90,
                },
            )
            if not created and player_match.team_id != team.id:
                player_match.team = team
            player_match.minute_off = min(player_match.minute_off, minute)
            player_match.save(update_fields=["team", "minute_off"] if not created else ["minute_off"])

        replacement_payload = ((event.get("substitution") or {}).get("replacement") or {})
        replacement = self.get_or_create_player(replacement_payload, team)
        if replacement:
            player_match, created = PlayerMatch.objects.get_or_create(
                player=replacement,
                match=match,
                defaults={
                    "team": team,
                    "is_starter": False,
                    "minute_on": minute,
                    "minute_off": 90,
                },
            )
            if player_match.team_id != team.id:
                player_match.team = team
            player_match.is_starter = False
            player_match.minute_on = minute
            player_match.minute_off = max(player_match.minute_off, minute)
            player_match.save(update_fields=["team", "is_starter", "minute_on", "minute_off"])

    @staticmethod
    def get_or_create_player(player_payload, team):
        player_id = player_payload.get("id")
        player_name = player_payload.get("name")
        if player_id is None or not player_name:
            return None

        player, _ = Player.objects.get_or_create(
            external_id=player_id,
            defaults={
                "name": player_name,
                "team_now": team,
            },
        )
        return player

    @staticmethod
    def resolve_team(match, team_name):
        if match.home_team.name == team_name:
            return match.home_team
        if match.away_team.name == team_name:
            return match.away_team
        if match.home_team.name.lower() == team_name.lower():
            return match.home_team
        if match.away_team.name.lower() == team_name.lower():
            return match.away_team

        return None
