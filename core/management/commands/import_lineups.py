"""Management command to import lineups."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.exceptions import MultipleObjectsReturned

from core.models.match import Match
from core.models.player import Player
from core.models.player_match import PlayerMatch


class Command(BaseCommand):
    help = "Import StatsBomb lineups"

    def add_arguments(self, parser):
        parser.add_argument(
            "--lineups-dir",
            default="",
            help=(
                "Directory containing StatsBomb lineup JSON files. "
                "Defaults to STATSBOMB_DATA_DIR/lineups."
            ),
        )

    def resolve_team(self, match, team_data):
        team_name = team_data["team_name"].lower()
        home = match.home_team.name.lower()
        away = match.away_team.name.lower()

        if team_name in home or home in team_name:
            return match.home_team
        if team_name in away or away in team_name:
            return match.away_team

        self.stdout.write(
            self.style.WARNING(
                f"Team name mismatch for match {match.match_id}: "
                f"StatsBomb='{team_data['team_name']}', "
                f"home='{match.home_team.name}', away='{match.away_team.name}'"
            )
        )
        return None

    def upsert_player_match(self, player, match, team, is_starter, minute_on = 0, minute_off = 90):
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
            duplicates = PlayerMatch.objects.filter(player=player, match=match).order_by("id")
            keeper = duplicates.first()
            duplicates.exclude(pk=keeper.pk).delete()

            for field, value in defaults.items():
                setattr(keeper, field, value)
            keeper.save(update_fields=[*defaults.keys(), "updated_at"])

    def handle(self, *args, **options):
        lineups_dir = Path(options["lineups_dir"] or settings.STATSBOMB_DATA_DIR / "lineups")

        if not lineups_dir.exists():
            self.stderr.write(f"Lineups dir not found: {lineups_dir}")
            return

        matches = Match.objects.all()

        for match in matches:
            path = lineups_dir / f"{match.match_id}.json"

            if not path.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"Lineup file missing for match {match.match_id}: {path}"
                    )
                )
                continue

            with path.open(encoding="utf-8") as f:
                lineups = json.load(f)

            for team_data in lineups:
                team = self.resolve_team(match, team_data)
                if team is None:
                    continue

                players = team_data["lineup"]

                for index, p in enumerate(players):
                    player, _ = Player.objects.update_or_create(
                        external_id=p["player_id"],
                        defaults={
                            "name": p["player_name"],
                            "team_now": team,
                        },
                    )

                    self.upsert_player_match(
                        player=player,
                        match=match,
                        team=team,
                        is_starter=index < 11,
                    )

            self.stdout.write(f"Imported lineup {match.match_id}")

        self.stdout.write(self.style.SUCCESS("Lineups imported"))
