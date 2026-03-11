import os
import json

from django.conf import settings
from django.core.management.base import BaseCommand

from futball.models.player import Player, PlayerMatch
from futball.models.team import Team
from futball.models.match import Match


class Command(BaseCommand):
    help = "Import players and player-match relationships from StatsBomb lineups"

    def handle(self, *args, **kwargs):

        lineups_dir = os.path.join(settings.STATSBOMB_DATA_DIR, "lineups")

        for file in os.listdir(lineups_dir):

            if not file.endswith(".json"):
                continue

            match_id = int(file.replace(".json", ""))

            try:
                match = Match.objects.get(match_id=match_id)
            except Match.DoesNotExist:
                continue

            path = os.path.join(lineups_dir, file)

            with open(path) as f:
                data = json.load(f)

            for team_data in data:

                team_name = team_data["team_name"]

                try:
                    team = Team.objects.get(name=team_name)
                except Team.DoesNotExist:
                    continue

                for p in team_data["lineup"]:

                    player, _ = Player.objects.get_or_create(
                        external_id=p["player_id"],
                        defaults={
                            "name": p["player_name"],
                            "team_now": team
                        }
                    )

                    positions = p.get("positions", [])
                    is_starter = len(positions) > 0

                    PlayerMatch.objects.get_or_create(
                        player=player,
                        match=match,
                        defaults={
                            "team": team,
                            "is_starter": is_starter
                        }
                    )

            self.stdout.write(self.style.SUCCESS(f"Imported match {match_id}"))