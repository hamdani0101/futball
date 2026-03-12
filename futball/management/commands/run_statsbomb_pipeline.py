"""Management command to run the StatsBomb import pipeline."""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the full StatsBomb pipeline in the required order"

    pipeline_steps = (
        "import_matches",
        "import_players",
        "import_lineups",
        "fetch_statsbomb_events",
        "import_shots",
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            default="all",
            help="Dataset argument for import_matches (default: all)",
        )
        parser.add_argument(
            "--matches-json",
            default="",
            help="Path to StatsBomb matches.json",
        )
        parser.add_argument(
            "--team-map",
            default="",
            help="Path to team_map.csv",
        )
        parser.add_argument(
            "--events-dir",
            default="",
            help="Directory where copied event JSON files are stored",
        )
        parser.add_argument(
            "--lineups-dir",
            default="",
            help=(
                "Directory containing StatsBomb lineup JSON files. "
                "Defaults to STATSBOMB_DATA_DIR/lineups."
            ),
        )
        parser.add_argument(
            "--open-data-root",
            default="",
            help=(
                "Path to the StatsBomb open-data repository root or its data "
                "directory. Defaults to STATSBOMB_DATA_DIR."
            ),
        )
        parser.add_argument(
            "--replace-shots",
            action="store_true",
            help="Delete existing shots for each match before importing",
        )

    def handle(self, *args, **options):
        matches_json = options["matches_json"] or settings.STATSBOMB_DATA_DIR / "shots" / "matches.json"
        team_map = options["team_map"] or settings.STATSBOMB_DATA_DIR / "shots" / "team_map.csv"
        events_dir = options["events_dir"] or settings.STATSBOMB_DATA_DIR / "shots" / "events"
        lineups_dir = options["lineups_dir"] or settings.STATSBOMB_DATA_DIR / "lineups"
        open_data_root = options["open_data_root"] or settings.STATSBOMB_DATA_DIR
        dataset = options["dataset"]

        self.stdout.write(
            self.style.WARNING(
                "Pipeline order: " + " -> ".join(self.pipeline_steps)
            )
        )

        self.run_step(
            "import_matches",
            dataset,
            statsbomb_matches=matches_json,
            team_map=team_map,
        )
        self.run_step("import_players", lineups_dir=lineups_dir)
        self.run_step("import_lineups", lineups_dir=lineups_dir)
        self.run_step(
            "fetch_statsbomb_events",
            out_dir=events_dir,
            open_data_root=open_data_root,
        )

        shots_kwargs = {"replace": options["replace_shots"]} if options["replace_shots"] else {}
        self.run_step("import_shots", events_dir, **shots_kwargs)

        self.stdout.write(self.style.SUCCESS("StatsBomb pipeline completed."))

    def run_step(self, command_name, *args, **kwargs):
        self.stdout.write(self.style.WARNING(f"\n>>> Starting {command_name}"))
        call_command(command_name, *args, **kwargs)
        self.stdout.write(self.style.SUCCESS(f"<<< Finished {command_name}"))
