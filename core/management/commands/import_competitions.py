import json
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
from rich.status import Status
from typing import Dict

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models.competition import Competition
from core.models.season import Season


class Command(BaseCommand):
    help = "Import competitions and seasons from StatsBomb competitions.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            required=True,
            help="Path to competitions.json",
        )

    # =====================
    # ENTRY
    # =====================

    def handle(self, *args, **options):
        
        path = options["path"]
        self.import_competitions(path)

        self.stderr.write("Import competitions completed 🎉")

    # =====================
    # CORE IMPORT
    # =====================

    @transaction.atomic
    def import_competitions(self, path: str):
        console = Console()
        with Status("Loading competitions...", console=console):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            
        if not isinstance(data, list):
            self.stderr.write("Invalid competitions.json format")
            return

        created_comp = updated_comp = 0
        created_season = updated_season = 0
        
        competition_cache = {}
        season_cache = {}
        
        with Progress(console=console) as progress:
            task = progress.add_task("Importing competitions...", total=len(data))

            for item in data:
                try:
                    if not item.get("competition_id") or not item.get("season_id"):
                        console.log("[yellow]Invalid record skipped[/yellow]")
                        progress.advance(task)
                        continue

                    competition, comp_created = self.upsert_competition(item, competition_cache)
                    season, season_created = self.upsert_season(item, competition, season_cache)

                    if comp_created:
                        created_comp += 1
                    else:
                        updated_comp += 1

                    if season_created:
                        created_season += 1
                    else:
                        updated_season += 1

                    progress.advance(task)

                except Exception as e:
                    console.log(f"[red]Error:[/red] {e}")
                    progress.advance(task)
        
        table = Table(title="Import Summary")

        table.add_column("Type", style="cyan")
        table.add_column("Created", style="green")
        table.add_column("Updated", style="yellow")

        table.add_row("Competitions", str(created_comp), str(updated_comp))
        table.add_row("Seasons", str(created_season), str(updated_season))

        console.print(table)

    # =====================
    # UPSERT LOGIC
    # =====================

    def upsert_competition(self, item: Dict, cache: Dict):
        comp_id = item.get("competition_id")

        if comp_id in cache:
            return cache[comp_id], False

        name = item.get("competition_name")
        country = item.get("country_name")
        gender = item.get("competition_gender")

        competition, created = Competition.objects.get_or_create(
            external_id=comp_id,
            defaults={
                "name": name,
                "country": country,
                "gender": gender,
            },
        )

        if not created:
            updated = False

            if name and competition.name != name:
                competition.name = name
                updated = True

            if country and competition.country != country:
                competition.country = country
                updated = True

            if gender and competition.gender != gender:
                competition.gender = gender
                updated = True

            if updated:
                competition.save()

        cache[comp_id] = competition
        return competition, created

    def upsert_season(self, item: Dict, competition: Competition, cache: Dict):
        season_id = item.get("season_id")

        if season_id in cache:
            return cache[season_id], False

        season_name = item.get("season_name")

        season, created = Season.objects.get_or_create(
            external_id=season_id,
            defaults={
                "competition": competition,
                "name": season_name,
            },
        )

        if not created:
            updated = False

            if season.name != season_name:
                season.name = season_name
                updated = True

            if season.competition_id != competition.id:
                season.competition = competition
                updated = True

            if updated:
                season.save()

        cache[season_id] = season
        return season, created