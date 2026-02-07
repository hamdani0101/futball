import json
from django.core.management.base import BaseCommand
from app.models import Match, Team, Player, PlayerMatch


class Command(BaseCommand):
    help = "Import StatsBomb lineups.json"

    def handle(self, *args, **kwargs):
        matches = Match.objects.all()

        for match in matches:
            path = f"data/lineups/{match.match_id}.json"

            try:
                with open(path) as f:
                    lineups = json.load(f)
            except FileNotFoundError:
                self.stdout.write(f"Lineup not found for match {match.match_id}")
                continue

            for team_data in lineups:
                team_name = team_data["team"]["name"]
                team = Team.objects.get(name=team_name)

                for p in team_data["lineup"]:
                    ext_id = p["player"]["id"]
                    name = p["player"]["name"]
                    position = p.get("position", {}).get("name", "")

                    player, _ = Player.objects.get_or_create(
                        external_id=ext_id,
                        defaults={
                            "name": name,
                            "team": team,
                            "position": position,
                        }
                    )

                    PlayerMatch.objects.get_or_create(
                        player=player,
                        match=match,
                        team=team,
                        defaults={
                            "is_starter": True,
                            "minute_on": 0,
                            "minute_off": 90,
                        }
                    )

        self.stdout.write(self.style.SUCCESS("Lineups imported successfully"))
