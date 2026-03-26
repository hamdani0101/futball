"""Management command to import substitution events into PlayerMatch rows."""

import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned
from django.core.management.base import BaseCommand

from core.models.event import Event
from core.models.match import Match
from core.models.player import Player
from core.models.player_match import PlayerMatch
from core.models.substitution import Substitution


class Command(BaseCommand):
    help = "Import StatsBomb substitutions and update PlayerMatch minute_on/minute_off"

    def add_arguments(self, parser):
        parser.add_argument(
            "--events-dir",
            default="",
            help=(
                "Directory containing StatsBomb event JSON files. "
                "Defaults to STATSBOMB_DATA_DIR/events."
            ),
        )
        parser.add_argument(
            "--match-id",
            default="",
            help="Optional single match_id to import.",
        )

    def _resolve_team(self, match, team_data):
        team_id = team_data.get("id")
        team_name = (team_data.get("name") or "").strip().lower()

        if team_id and match.home_team.external_id == team_id:
            return match.home_team
        if team_id and match.away_team.external_id == team_id:
            return match.away_team

        home_name = (match.home_team.name or "").strip().lower()
        away_name = (match.away_team.name or "").strip().lower()

        if team_name and (team_name in home_name or home_name in team_name):
            return match.home_team
        if team_name and (team_name in away_name or away_name in team_name):
            return match.away_team

        self.stdout.write(
            self.style.WARNING(
                f"Team mismatch for match {match.external_id}: "
                f"event='{team_data}', home='{match.home_team.name}', away='{match.away_team.name}'"
            )
        )
        return None

    def _get_or_create_player(self, player_data, team):
        player_id = player_data.get("id")
        player_name = (player_data.get("name") or "Unknown").strip() or "Unknown"

        if player_id is not None:
            player, created = Player.objects.get_or_create(
                external_id=player_id,
                defaults={
                    "name": player_name,
                    "team_now": team,
                },
            )
            update_fields = []
            if not created and player.name != player_name:
                player.name = player_name
                update_fields.append("name")
            if player.team_now_id != team.id:
                player.team_now = team
                update_fields.append("team_now")
            if update_fields:
                player.save(update_fields=update_fields)
            return player

        player = Player.objects.filter(name=player_name, team_now=team).first()
        if player:
            return player

        return Player.objects.create(
            name=player_name,
            team_now=team,
        )

    def _upsert_player_match(self, player, match, team, is_starter, minute_on, minute_off):
        defaults = {
            "team": team,
            "is_starter": is_starter,
            "minute_on": minute_on,
            "minute_off": minute_off,
        }
        try:
            PlayerMatch.objects.update_or_create(
                player=player,
                match=match,
                defaults=defaults,
            )
        except MultipleObjectsReturned:
            rows = PlayerMatch.objects.filter(player=player, match=match).order_by("id")
            keeper = rows.first()
            rows.exclude(pk=keeper.pk).delete()
            for field, value in defaults.items():
                setattr(keeper, field, value)
            keeper.save(update_fields=[*defaults.keys(), "updated_at"])

    def _upsert_event(self, match, team, player_off, event):
        event_index = int(event.get("index") or 0)
        defaults = {
            "match": match,
            "team": team,
            "player": player_off,
            "period": int(event.get("period") or 1),
            "minute": int(event.get("minute") or 0),
            "second": int(event.get("second") or 0),
            "event_index": event_index,
            "possession": int(event.get("possession") or 0),
            "timestamp": (event.get("timestamp") or None),
            "type": Event.Type.SUBSTITUTION,
            "play_pattern": ((event.get("play_pattern") or {}).get("name") or "").strip(),
        }
        external_event_id = event.get("id")
        if external_event_id:
            obj, _ = Event.objects.update_or_create(
                external_event_id=str(external_event_id),
                defaults=defaults,
            )
            return obj

        obj, _ = Event.objects.update_or_create(
            match=match,
            event_index=event_index,
            defaults=defaults,
        )
        return obj

    def _upsert_substitution(self, event_row, match, team, player_off, player_on, event):
        defaults = {
            "match": match,
            "team": team,
            "player_out": player_off,
            "player_in": player_on,
            "minute": int(event.get("minute") or 0),
            "second": int(event.get("second") or 0),
            "period": int(event.get("period") or 1),
            "reason": ((event.get("substitution") or {}).get("outcome") or {}).get("name", ""),
        }
        Substitution.objects.update_or_create(
            event=event_row,
            defaults=defaults,
        )

    def _match_end_minute(self, events):
        has_extra_time = any((event.get("period") or 1) in [3, 4, 5] for event in events)
        return 120 if has_extra_time else 90

    def _import_match(self, match, event_path):
        with event_path.open(encoding="utf-8") as handle:
            events = json.load(handle)

        if not isinstance(events, list):
            self.stdout.write(
                self.style.WARNING(f"Skip {event_path.name}: JSON is not a list of events")
            )
            return 0

        match_end_minute = self._match_end_minute(events)
        imported = 0

        for event in events:
            event_type = (event.get("type") or {}).get("name")
            if event_type != "Substitution":
                continue

            team = self._resolve_team(match, event.get("team") or {})
            if team is None:
                continue

            player_off_data = event.get("player") or {}
            replacement_data = ((event.get("substitution") or {}).get("replacement") or {})
            if not player_off_data or not replacement_data:
                continue

            minute = int(event.get("minute") or 0)
            player_off = self._get_or_create_player(player_off_data, team)
            player_on = self._get_or_create_player(replacement_data, team)
            event_row = self._upsert_event(match, team, player_off, event)

            off_row = PlayerMatch.objects.filter(player=player_off, match=match).first()
            off_minute_on = off_row.minute_on if off_row else 0
            off_is_starter = off_row.is_starter if off_row else minute == 0
            self._upsert_player_match(
                player=player_off,
                match=match,
                team=team,
                is_starter=off_is_starter,
                minute_on=off_minute_on,
                minute_off=minute,
            )

            on_row = PlayerMatch.objects.filter(player=player_on, match=match).first()
            on_minute_off = on_row.minute_off if on_row and on_row.minute_off > minute else match_end_minute
            self._upsert_player_match(
                player=player_on,
                match=match,
                team=team,
                is_starter=False,
                minute_on=minute,
                minute_off=on_minute_off,
            )
            self._upsert_substitution(
                event_row=event_row,
                match=match,
                team=team,
                player_off=player_off,
                player_on=player_on,
                event=event,
            )
            imported += 1

        return imported

    def handle(self, *args, **options):
        events_dir = Path(options["events_dir"] or settings.STATSBOMB_DATA_DIR / "events")
        match_id = (options.get("match_id") or "").strip()

        if not events_dir.exists():
            self.stderr.write(f"Events dir not found: {events_dir}")
            return

        matches = Match.objects.select_related("home_team", "away_team").order_by("external_id")
        if match_id:
            matches = matches.filter(external_id=match_id)

        if not matches.exists():
            self.stdout.write(self.style.WARNING("No matches found to import substitutions."))
            return

        total_imported = 0
        for match in matches:
            event_path = events_dir / f"{match.external_id}.json"
            if not event_path.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"Event file missing for match {match.external_id}: {event_path}"
                    )
                )
                continue

            imported = self._import_match(match, event_path)
            total_imported += imported
            self.stdout.write(
                self.style.SUCCESS(
                    f"Imported {imported} substitutions for match {match.external_id}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f"Substitutions imported: {total_imported}")
        )
