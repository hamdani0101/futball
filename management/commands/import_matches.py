import csv
from datetime import datetime
from django.core.management.base import BaseCommand
from futball.models import Competition, Season, Team, Match


class Command(BaseCommand):
    help = "Import match data from Football-Data style CSV"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str)
        parser.add_argument(
            "--competition",
            type=str,
            default="Premier League",
            help="Competition name",
        )
        parser.add_argument(
            "--season",
            type=str,
            default="2024/2025",
            help="Season name",
        )

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        competition_name = options["competition"]
        season_name = options["season"]

        competition, _ = Competition.objects.get_or_create(
            name=competition_name
        )
        season, _ = Season.objects.get_or_create(
            competition=competition,
            name=season_name,
        )

        self.stdout.write(
            self.style.WARNING(
                f"Importing matches: {competition_name} {season_name}"
            )
        )

        with open(csv_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                home_team, _ = Team.objects.get_or_create(
                    name=row["HomeTeam"]
                )
                away_team, _ = Team.objects.get_or_create(
                    name=row["AwayTeam"]
                )

                match_date = datetime.strptime(
                    row["Date"], "%d/%m/%y"
                ).date()

                match_key = f"{row['Date']}-{row['HomeTeam']}-{row['AwayTeam']}"

                Match.objects.get_or_create(
                    match_id=match_key,
                    defaults={
                        "season": season,
                        "home_team": home_team,
                        "away_team": away_team,
                        "match_date": match_date,
                        "home_score": int(row["FTHG"]),
                        "away_score": int(row["FTAG"]),

                        "home_shots": int(row.get("HS", 0) or 0),
                        "away_shots": int(row.get("AS", 0) or 0),
                        "home_shots_on_target": int(row.get("HST", 0) or 0),
                        "away_shots_on_target": int(row.get("AST", 0) or 0),
                    },
                )



        self.stdout.write(self.style.SUCCESS("Match import completed"))
