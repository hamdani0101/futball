import csv
import json
import os
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from futball.models.competition import Competition
from futball.models.season import Season
from futball.models.match import Match, MatchTeamStats
from futball.models.team import Team

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
        parser.add_argument(
            "--statsbomb-matches",
            type=str,
            default="",
            help=(
                "Path to StatsBomb matches.json to align match_id with "
                "StatsBomb match ids"
            ),
        )
        parser.add_argument(
            "--team-map",
            type=str,
            default="",
            help=(
                "Optional CSV map with headers "
                "`statsbomb_name,csv_name` to normalize team names"
            ),
        )

    def get_datasets(self, dataset_arg):
        data_root = os.path.join(settings.BASE_DIR, "data", "match")

        if dataset_arg == "all":
            datasets = []
            for d in os.listdir(data_root):
                dataset_dir = os.path.join(data_root, d)
                if not os.path.isdir(dataset_dir):
                    continue
                if (
                    os.path.exists(os.path.join(dataset_dir, "datapackage.yaml"))
                    or os.path.exists(os.path.join(dataset_dir, "datapackage.json"))
                ):
                    datasets.append(d)
            return sorted(datasets)

        return [dataset_arg]
    
    def import_dataset(self, dataset, statsbomb_index):
        dataset_path = os.path.join(settings.BASE_DIR, "data", "match", dataset)

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
                statsbomb_index=statsbomb_index,
            )


        
    def load_datapackage(self, dataset_path):
        yaml_path = os.path.join(dataset_path, "datapackage.yaml")
        json_path = os.path.join(dataset_path, "datapackage.json")

        if os.path.exists(yaml_path):
            try:
                import yaml
            except ModuleNotFoundError as exc:
                raise ModuleNotFoundError(
                    "PyYAML is required to read datapackage.yaml"
                ) from exc

            with open(yaml_path, encoding="utf-8") as f:
                return yaml.safe_load(f)

        if os.path.exists(json_path):
            with open(json_path, encoding="utf-8") as f:
                return json.load(f)

        raise FileNotFoundError(
            f"No datapackage.yaml or datapackage.json in {dataset_path}"
        )


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
        statsbomb_index = self.load_statsbomb_index(
            options.get("statsbomb_matches") or "",
            options.get("team_map") or "",
        )

        if not datasets:
            self.stderr.write(
                self.style.ERROR("No datasets found")
            )
            return

        for dataset in datasets:
            self.stdout.write(
                self.style.WARNING(f"\n=== Importing dataset: {dataset} ===")
            )
            self.import_dataset(dataset, statsbomb_index)

        self.stdout.write(
            self.style.SUCCESS("\nAll dataset imports completed 🎉")
        )


    def import_csv(self, csv_path, season, date_format, encoding, statsbomb_index):
        created = updated = skipped = 0

        with open(csv_path, newline="", encoding=encoding) as f:
            reader = csv.DictReader(f)

            for row in reader:
                match_date = datetime.strptime(
                    row["Date"], date_format
                )
                match_id = self.resolve_match_id(
                    statsbomb_index=statsbomb_index,
                    match_date=match_date,
                    home_team=row["HomeTeam"],
                    away_team=row["AwayTeam"],
                    fallback_date=row["Date"],
                )

                home_team, _ = Team.objects.get_or_create(name=row["HomeTeam"])
                away_team, _ = Team.objects.get_or_create(name=row["AwayTeam"])

                home_goals = int(row.get("FTHG") or row.get("HG") or 0)
                away_goals = int(row.get("FTAG") or row.get("AG") or 0)

                match = Match.objects.filter(match_id=match_id).first()
                if match:
                    match.season = season
                    match.home_team = home_team
                    match.away_team = away_team
                    match.match_date = match_date
                    match.status = "finished"
                    match.save(
                        update_fields=[
                            "season",
                            "home_team",
                            "away_team",
                            "match_date",
                            "status",
                        ]
                    )
                    updated += 1
                else:
                    match = Match.objects.create(
                        match_id=match_id,
                        season=season,
                        home_team=home_team,
                        away_team=away_team,
                        match_date=match_date,
                        status="finished",
                    )
                    created += 1
                    
                MatchTeamStats.objects.update_or_create(
                    match=match,
                    team=home_team,
                    defaults={
                        "xg": 0.0,
                        "shots": int(row.get("HS") or 0),
                        "shots_on_target": int(row.get("HST") or 0),
                    },
                )
                MatchTeamStats.objects.update_or_create(
                    match=match,
                    team=away_team,
                    defaults={
                        "xg": 0.0,
                        "shots": int(row.get("AS") or 0),
                        "shots_on_target": int(row.get("AST") or 0),
                    },
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"{os.path.basename(csv_path)}: {created} created, {updated} updated, {skipped} skipped"
            )
        )

    # --------------------
    # StatsBomb helpers
    # --------------------

    @staticmethod
    def normalize_team(name):
        return (name or "").strip().lower()

    def load_statsbomb_index(self, matches_path, team_map_path):
        if not matches_path:
            return {}

        if not os.path.exists(matches_path):
            self.stderr.write(
                self.style.WARNING(
                    f"StatsBomb matches file not found: {matches_path}"
                )
            )
            return {}
        if os.path.getsize(matches_path) == 0:
            self.stderr.write(
                self.style.WARNING(
                    f"StatsBomb matches file is empty: {matches_path}"
                )
            )
            return {}

        team_map = {}
        if team_map_path and os.path.exists(team_map_path):
            with open(team_map_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sb = (row.get("statsbomb_name") or "").strip()
                    csv_name = (row.get("csv_name") or "").strip()
                    if sb and csv_name:
                        team_map[self.normalize_team(sb)] = csv_name

        try:
            with open(matches_path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            self.stderr.write(
                self.style.WARNING(
                    f"StatsBomb matches file is not valid JSON: {matches_path}"
                )
            )
            return {}

        index = {}
        for m in data:
            match_id = str(m.get("match_id") or "").strip()
            match_date = m.get("match_date")
            home = (m.get("home_team") or {}).get("home_team_name")
            away = (m.get("away_team") or {}).get("away_team_name")

            if not (match_id and match_date and home and away):
                continue

            home = team_map.get(self.normalize_team(home), home)
            away = team_map.get(self.normalize_team(away), away)

            index_key = (
                match_date,
                self.normalize_team(home),
                self.normalize_team(away),
            )
            index[index_key] = match_id

        return index

    def resolve_match_id(
        self,
        statsbomb_index,
        match_date,
        home_team,
        away_team,
        fallback_date,
    ):
        if statsbomb_index:
            key = (
                match_date.strftime("%Y-%m-%d"),
                self.normalize_team(home_team),
                self.normalize_team(away_team),
            )
            sb_id = statsbomb_index.get(key)
            if sb_id:
                return sb_id

        return f"{fallback_date}-{home_team}-{away_team}"
