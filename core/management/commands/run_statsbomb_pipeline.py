"""Management command to run the StatsBomb import pipeline."""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the full StatsBomb pipeline in the required order"

    pipeline_steps = (
        "import_competitions",
        "import_matches",
        "import_lineups",
        "import_shots",
        "import_passes",
        "import_substitution",
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="",
            help="Defaults to STATSBOMB_DATA_DIR/competition.json.",
        )
        parser.add_argument(
            "--matches-dir",
            default="",
            help="Defaults to STATSBOMB_DATA_DIR/matches.",
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
            "--replace-shots",
            action="store_true",
            help="Delete existing shots for each match before importing",
        )
        parser.add_argument(
            "--replace-passes",
            action="store_true",
            help="Delete existing passes for each match before importing",
        )

    def handle(self, *args, **options):
        path = options["path"] or settings.STATSBOMB_DATA_DIR / "competitions.json"
        events_dir = options["events_dir"] or settings.STATSBOMB_DATA_DIR / "events"
        lineups_dir = options["lineups_dir"] or settings.STATSBOMB_DATA_DIR / "lineups"
        base_dir = options["matches_dir"] or settings.STATSBOMB_DATA_DIR / "matches"

        self.stdout.write(
            self.style.WARNING(
                "Pipeline order: " + " -> ".join(self.pipeline_steps)
            )
        )
        
        self.run_step("import_competitions", path=path)

        self.run_step(
            "import_matches",
            base_dir=base_dir
        )
        self.run_step("import_lineups", lineups_dir=lineups_dir)
        
        self.run_step("import_substitution", events_dir=events_dir)

        shots_kwargs = {"replace": options["replace_shots"]} if options["replace_shots"] else {}
        self.run_step("import_shots", events_dir, **shots_kwargs)
        pass_kwargs = {"replace": options["replace_passes"]} if options["replace_passes"] else {}
        self.run_step("import_passes", events_dir, **pass_kwargs)

        self.stdout.write(self.style.SUCCESS("StatsBomb pipeline completed."))

    def run_step(self, command_name, *args, **kwargs):
        self.stdout.write(self.style.WARNING(f"\n>>> Starting {command_name}"))
        call_command(command_name, *args, **kwargs)
        self.stdout.write(self.style.SUCCESS(f"<<< Finished {command_name}"))
