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
        "import_events",
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
        self.run_step("import_events", events_dir=events_dir)
        self.run_step("import_substitution", events_dir=events_dir)

        self.stdout.write(self.style.SUCCESS("StatsBomb pipeline completed."))

    def run_step(self, command_name, *args, **kwargs):
        self.stdout.write(self.style.WARNING(f"\n>>> Starting {command_name}"))
        call_command(command_name, *args, **kwargs)
        self.stdout.write(self.style.SUCCESS(f"<<< Finished {command_name}"))
