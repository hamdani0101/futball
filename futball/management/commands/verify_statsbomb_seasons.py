import json
from pathlib import Path

from django.core.management.base import BaseCommand


DEFAULT_LEAGUE_MAP = {
    "bundesliga": "1. Bundesliga",
    "la-liga": "La Liga",
    "ligue-1": "Ligue 1",
    "premier-league": "Premier League",
    "serie-a": "Serie A",
}


class Command(BaseCommand):
    help = "Verify which StatsBomb seasons were found for each league"

    def add_arguments(self, parser):
        parser.add_argument(
            "--open-data-root",
            required=True,
            help="Path to the StatsBomb open-data repository root",
        )
        parser.add_argument(
            "--data-match-dir",
            default="data/match",
            help="Local datasets root (default: data/match)",
        )
        parser.add_argument(
            "--leagues",
            default="",
            help=(
                "Comma-separated league slugs to include "
                "(default: all folders in data/match)"
            ),
        )

    def handle(self, *args, **options):
        open_data_root = Path(options["open_data_root"])
        data_match_dir = Path(options["data_match_dir"])
        competitions_path = open_data_root / "data" / "competitions.json"
        matches_root = open_data_root / "data" / "matches"

        if not competitions_path.exists():
            self.stderr.write(
                self.style.ERROR(
                    f"competitions.json not found: {competitions_path}"
                )
            )
            return

        if options["leagues"]:
            league_slugs = [
                s.strip() for s in options["leagues"].split(",") if s.strip()
            ]
        else:
            league_slugs = self.list_datasets(data_match_dir)

        try:
            with open(competitions_path, encoding="utf-8") as f:
                competitions = json.load(f)
        except json.JSONDecodeError:
            self.stderr.write(
                self.style.ERROR(
                    f"competitions.json is not valid JSON: {competitions_path}"
                )
            )
            return
        if not isinstance(competitions, list):
            self.stderr.write(
                self.style.ERROR(
                    f"competitions.json does not contain a list: {competitions_path}"
                )
            )
            return

        self.stdout.write(self.style.WARNING("=== StatsBomb Seasons Found ==="))
        missing_map = []

        for slug in league_slugs:
            league_name = DEFAULT_LEAGUE_MAP.get(slug)
            if not league_name:
                missing_map.append(slug)
                continue

            seasons = []
            missing_files = 0

            for comp in competitions:
                if comp.get("competition_name") != league_name:
                    continue

                comp_id = comp.get("competition_id")
                season_id = comp.get("season_id")
                season_name = comp.get("season_name")

                if comp_id is None or season_id is None:
                    continue

                match_file = matches_root / str(comp_id) / f"{season_id}.json"
                if match_file.exists():
                    seasons.append(season_name or str(season_id))
                else:
                    missing_files += 1

            seasons_sorted = sorted(set(seasons))
            seasons_display = ", ".join(seasons_sorted) if seasons_sorted else "-"

            self.stdout.write(
                f"{slug} ({league_name}): {len(seasons_sorted)} seasons"
            )
            self.stdout.write(f"  {seasons_display}")

            if missing_files:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Missing match files: {missing_files}"
                    )
                )

        if missing_map:
            self.stdout.write(self.style.WARNING("\nNo league mapping for:"))
            for slug in missing_map:
                self.stdout.write(f"- {slug}")

    @staticmethod
    def list_datasets(data_match_dir: Path):
        if not data_match_dir.exists():
            return []
        return sorted(
            d.name for d in data_match_dir.iterdir() if d.is_dir()
        )
