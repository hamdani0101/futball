from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Min

from futball.models.season import Season
from futball.models.match import Match
from futball.models.competition import Competition


class Command(BaseCommand):
    help = "Merge duplicate seasons (same competition + name) into one season"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without writing to the DB",
        )
        parser.add_argument(
            "--competition",
            type=str,
            help="Limit merge to a competition name (exact match)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        competition_name = options["competition"]

        seasons_qs = Season.objects.all()
        if competition_name:
            comp = Competition.objects.filter(name=competition_name).first()
            if not comp:
                self.stdout.write(
                    self.style.WARNING(
                        f"Competition not found: {competition_name}"
                    )
                )
                return
            seasons_qs = seasons_qs.filter(competition=comp)

        duplicates = (
            seasons_qs.values("competition_id", "name")
            .annotate(count=Count("id"), keep_id=Min("id"))
            .filter(count__gt=1)
        )

        merged = 0
        skipped = 0

        for dup in duplicates:
            competition_id = dup["competition_id"]
            season_name = dup["name"]
            keep_id = dup["keep_id"]

            target = Season.objects.filter(id=keep_id).first()
            if not target:
                skipped += 1
                continue

            sources = (
                Season.objects.filter(
                    competition_id=competition_id,
                    name=season_name,
                )
                .exclude(id=keep_id)
                .order_by("id")
            )

            for source in sources:
                if dry_run:
                    self.stdout.write(
                        f"[DRY RUN] Would merge Season id={source.id} "
                        f"'{source.name}' -> id={target.id}"
                    )
                    merged += 1
                    continue

                with transaction.atomic():
                    Match.objects.filter(season=source).update(season=target)
                    source.delete()

                merged += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Merged Season id={source.id} into id={target.id}"
                    )
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: {merged} merges, {skipped} skipped."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {merged} merged, {skipped} skipped."
            )
        )
