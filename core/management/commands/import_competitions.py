import json
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

        self.stdout.write(self.style.SUCCESS("Import competitions completed 🎉"))

    # =====================
    # CORE IMPORT
    # =====================

    @transaction.atomic
    def import_competitions(self, path: str):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        created_comp = updated_comp = 0
        created_season = updated_season = 0

        for item in data:
            try:
                competition, comp_created = self.upsert_competition(item)
                season, season_created = self.upsert_season(item, competition)

                if comp_created:
                    created_comp += 1
                else:
                    updated_comp += 1

                if season_created:
                    created_season += 1
                else:
                    updated_season += 1

            except Exception as e:
                self.stderr.write(f"Error: {e}")

        self.stdout.write(
            f"Competitions → created={created_comp}, updated={updated_comp}"
        )
        self.stdout.write(
            f"Seasons → created={created_season}, updated={updated_season}"
        )

    # =====================
    # UPSERT LOGIC
    # =====================

    def upsert_competition(self, item: Dict):
        name = item.get("competition_name")
        country = item.get("country_name")
        gender = item.get("competition_gender")

        competition, created = Competition.objects.update_or_create(
            external_id=item.get("competition_id"),
            defaults={
                "name": name,
                "country": country,
                "gender": gender,
            },
        )

        if not created:
            updated = False

            if country and competition.country != country:
                competition.country = country
                updated = True

            if updated:
                competition.save()

        return competition, created

    def upsert_season(self, item: Dict, competition: Competition):
        season_name = item.get("season_name")

        season, created = Season.objects.update_or_create(
            external_id=item.get("season_id"),
            defaults={
                "competition": competition,
                "name": season_name,
            },
        )

        return season, created