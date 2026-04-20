from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn


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
        parser.add_argument("--path", default="")
        parser.add_argument("--matches-dir", default="")
        parser.add_argument("--events-dir", default="")
        parser.add_argument("--lineups-dir", default="")

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

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
        ) as progress:

            main_task = progress.add_task(
                "[cyan]Running StatsBomb Pipeline...",
                total=len(self.pipeline_steps),
            )

            self.run_step(progress, main_task, "import_competitions", path=path)

            self.run_step(progress, main_task, "import_matches", base_dir=base_dir)

            self.run_step(progress, main_task, "import_lineups", lineups_dir=lineups_dir)

            self.run_step(progress, main_task, "import_events")

            self.run_step(
                progress,
                main_task,
                "import_substitution",
                events_dir=events_dir,
            )

        self.stdout.write(self.style.SUCCESS("StatsBomb pipeline completed."))

    def run_step(self, progress, main_task, command_name, *args, **kwargs):
        progress.console.print(f"\n[bold yellow]>>> Starting {command_name}")

        call_command(command_name, *args, **kwargs)

        progress.console.print(f"[bold green]<<< Finished {command_name}")

        progress.update(main_task, advance=1)