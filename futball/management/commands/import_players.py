import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from futball.models.player import Player
from futball.models.match import Match


class Command(BaseCommand):
    help = "Import players and player-match relationships from StatsBomb lineups"

    @staticmethod
    def resolve_team(match, team_data):
        team_name = team_data["team"]["name"].lower()
        home = match.home_team.name.lower()
        away = match.away_team.name.lower()

        if team_name in home or home in team_name:
            return match.home_team
        if team_name in away or away in team_name:
            return match.away_team
        return None

    def add_arguments(self, parser):
        parser.add_argument(
            "--lineups-dir",
            default="",
            help=(
                "Directory containing StatsBomb lineup JSON files. "
                "Defaults to STATSBOMB_DATA_DIR/lineups."
            ),
        )

    def handle(self, *args, **options):
        lineups_dir = Path(options["lineups_dir"] or settings.STATSBOMB_DATA_DIR / "lineups")
        if not lineups_dir.is_dir():
            self.stderr.write(
                self.style.ERROR(f"Lineups directory not found: {lineups_dir}")
            )
            return

        for file_path in sorted(lineups_dir.iterdir()):
            if file_path.suffix != ".json":
                continue

            match_id = file_path.stem

            try:
                match = Match.objects.get(match_id=match_id)
            except Match.DoesNotExist:
                continue

            with file_path.open(encoding="utf-8") as f:
                data = json.load(f)

            for team_data in data:
                team = self.resolve_team(match, team_data)
                if team is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Team mismatch for match {match_id}: "
                            f"{team_data['team']['name']}"
                        )
                    )
                    continue

                for p in team_data["lineup"]:
                    Player.objects.update_or_create(
                        external_id=p["player_id"],
                        defaults={
                            "name": p["player_name"],
                            "team_now": team,
                        },
                    )

            self.stdout.write(self.style.SUCCESS(f"Imported match {match_id}"))
