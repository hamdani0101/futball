import csv
import json
import os
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from futball.models import Competition, Season, Team, Match


SCHEMA_FIELD_MAP = {
    "Date": "date",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "FTHG": "home_score",
    "FTAG": "away_score",
    "HS": "home_shots",
    "AS": "away_shots",
    "HST": "home_shots_on_target",
    "AST": "away_shots_on_target",
}

COUNTRY_MAP = {
    "bundesliga": "Germany",
    "german bundesliga": "Germany",
    "english premier league": "England",
    "spanish la liga": "Spain",
    "italian serie a": "Italy",
    "french ligue 1": "France",
}


class Command(BaseCommand):
    help = "Import match dataset using schema.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "dataset",
            type=str,
            help="Dataset name (e.g. bundesliga) or 'all'",
        )

    def get_datasets(self, dataset_arg):
        data_root = os.path.join(settings.BASE_DIR, "data")

        if dataset_arg == "all":
            return [
                d for d in os.listdir(data_root)
                if os.path.isdir(os.path.join(data_root, d))
                and os.path.exists(
                    os.path.join(data_root, d, "datapackage.json")
                )
            ]

        return [dataset_arg]
    
    def import_dataset(self, dataset):
        dataset_path = os.path.join(settings.BASE_DIR, "data", dataset)

        datapackage = self.load_datapackage(dataset_path)

        competition_name = datapackage.get("title", dataset)
        key = datapackage.get("name", "").replace("-", " ").lower()
        country = COUNTRY_MAP.get(key)

        competition, created = Competition.objects.get_or_create(
            name=competition_name,
            defaults={"country": country},
        )

        if not created and country and not competition.country:
            competition.country = country
            competition.save(update_fields=["country"])

        for resource in datapackage["resources"]:
            csv_path = os.path.join(dataset_path, resource["path"])
            encoding = resource.get("encoding", "utf-8")

            schema = resource["schema"]
            date_format = next(
                f["format"]
                for f in schema["fields"]
                if f["name"] == "Date"
            )

            season_name = self.parse_season_from_resource(resource["name"])

            season, _ = Season.objects.get_or_create(
                competition=competition,
                name=season_name,
            )

            self.import_csv(
                csv_path=csv_path,
                season=season,
                date_format=date_format,
                encoding=encoding,
            )


        
    def load_datapackage(self, dataset_path):
        path = os.path.join(dataset_path, "datapackage.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)


    # --------------------
    # Helpers
    # --------------------

    @staticmethod
    def parse_season_from_resource(name):
        # season-9900 → 1999/2000
        code = name.replace("season-", "")

        start_year = int(code[:2])
        end_year = int(code[2:])

        start = 1900 + start_year if start_year >= 90 else 2000 + start_year
        end = 1900 + end_year if end_year >= 90 else 2000 + end_year

        return f"{start}/{end}"


    def load_schema(self, dataset_path):
        schema_path = os.path.join(dataset_path, "schema.json")
        with open(schema_path, encoding="utf-8") as f:
            return json.load(f)

    # --------------------
    # Main
    # --------------------

    def handle(self, *args, **options):
        datasets = self.get_datasets(options["dataset"])

        if not datasets:
            self.stderr.write(
                self.style.ERROR("No datasets found")
            )
            return

        for dataset in datasets:
            self.stdout.write(
                self.style.WARNING(f"\n=== Importing dataset: {dataset} ===")
            )
            self.import_dataset(dataset)

        self.stdout.write(
            self.style.SUCCESS("\nAll dataset imports completed 🎉")
        )


    def import_csv(self, csv_path, season, date_format, encoding):
        created = skipped = 0

        with open(csv_path, newline="", encoding=encoding) as f:
            reader = csv.DictReader(f)

            for row in reader:
                match_id = f"{row['Date']}-{row['HomeTeam']}-{row['AwayTeam']}"

                if Match.objects.filter(match_id=match_id).exists():
                    skipped += 1
                    continue

                home_team, _ = Team.objects.get_or_create(name=row["HomeTeam"])
                away_team, _ = Team.objects.get_or_create(name=row["AwayTeam"])

                match_date = datetime.strptime(
                    row["Date"], date_format
                ).date()

                Match.objects.create(
                    match_id=match_id,
                    season=season,
                    home_team=home_team,
                    away_team=away_team,
                    match_date=match_date,
                    home_score=int(row.get("FTHG") or 0),
                    away_score=int(row.get("FTAG") or 0),
                    home_shots=int(row.get("HS") or 0),
                    away_shots=int(row.get("AS") or 0),
                    home_shots_on_target=int(row.get("HST") or 0),
                    away_shots_on_target=int(row.get("AST") or 0),
                )

                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{os.path.basename(csv_path)}: {created} created, {skipped} skipped"
            )
        )

