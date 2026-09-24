import time
from django.core.management.base import BaseCommand
from django.db.models import F
from core.models import Event, Match, MatchTeamStats


class Command(BaseCommand):
    help = "Replay match events like live"

    def add_arguments(self, parser):
        parser.add_argument("match_id", type=int)
        parser.add_argument("--speed", type=float, default=0.2)

    def handle(self, *args, **options):
        match_id = options["match_id"]
        speed = options["speed"]

        match = Match.objects.get(id=match_id)

        self.reset_match_state(match)

        events = Event.objects.filter(match=match).order_by(
            "period", "minute", "second", "event_index", "id",
        )

        self.stdout.write(self.style.SUCCESS(f"Replaying match {match.id}..."))

        for event in events:
            from analytics.services.live_match_stats import update_live_match_stats
            update_live_match_stats(event)

            home_score = MatchTeamStats.objects.filter(
                match=match, team=match.home_team,
            ).values_list("goals", flat=True).first() or 0
            away_score = MatchTeamStats.objects.filter(
                match=match, team=match.away_team,
            ).values_list("goals", flat=True).first() or 0

            self.stdout.write(
                f"[{event.minute}:{event.second:02d}] "
                f"{event.type} | Score: {home_score}-{away_score}"
            )

            time.sleep(speed)

    def reset_match_state(self, match):
        MatchTeamStats.objects.filter(match=match).update(
            goals=0,
            xg=0.0,
            shots=0,
            shots_on_target=0,
            passes=0,
            completed_passes=0,
            pass_accuracy=0.0,
            possession=0,
            possession_seconds=0.0,
            last_event=None,
        )
        Match.objects.filter(pk=match.pk).update(
            current_minute=0,
            current_second=0,
            period=1,
        )
