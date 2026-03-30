"""Management command to import lineups."""

import json
from pathlib import Path
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.exceptions import MultipleObjectsReturned

from core.models.match import Match
from core.models.player import Player
from core.models.player_match import PlayerMatch


class Command(BaseCommand):
    help = "Import StatsBomb lineups"
    console = Console()

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
        team_id = team_data.get("team_id")

        if match.home_team.external_id == team_id:
            return match.home_team

        if match.away_team.external_id == team_id:
            return match.away_team

        self.stdout.write(
            self.style.WARNING(
                f"Team ID mismatch for match {match.external_id}: {team_id}"
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

        files = list(lineups_dir.glob("*.json"))

        files = list(lineups_dir.glob("*.json"))

        with Progress() as progress:
            task = progress.add_task(
                "[cyan]Importing lineups...",
                total=len(files)
            )

            total_players = 0
            total_matches = 0
            total_skipped = 0

            for file in files:
                match_id = file.stem
                match = Match.objects.filter(external_id=match_id).first()

                if not match:
                    total_skipped += 1
                    progress.advance(task)
                    continue

                with file.open(encoding="utf-8") as f:
                    lineups = json.load(f)

                player_count = 0

                for team_data in lineups:
                    team = self.resolve_team(match, team_data)
                    if not team:
                        continue

                    for index, p in enumerate(team_data["lineup"]):
                        player, _ = Player.objects.update_or_create(
                            external_id=p["player_id"],
                            defaults={
                                "name": p["player_name"],
                                "team_now": team,
                                "country": p.get("country", {}).get("name", ""),
                            },
                        )

                        self.upsert_player_match(
                            player=player,
                            match=match,
                            team=team,
                            is_starter=index < 11,
                        )

                        player_count += 1

                total_players += player_count
                total_matches += 1

                progress.update(
                    task,
                    description=f"[cyan]Importing {file.name}[/cyan]"
                )
                progress.advance(task)
                
        table = Table(title="Lineup Import Summary")

        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Matches Processed", str(total_matches))
        table.add_row("Players Imported", str(total_players))
        table.add_row("Skipped Matches", str(total_skipped))

        self.console.print(table)
