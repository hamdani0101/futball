import time
from django.core.management.base import BaseCommand
from core.models import Event, Match, MatchState
from analytics.services.event_processor import process_event


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

        events = Event.objects.filter(match=match).order_by("event_index")

        self.stdout.write(self.style.SUCCESS(f"Replaying match {match.id}..."))

        for event in events:
            state = process_event(event)

            self.stdout.write(
                f"[{event.minute}:{event.second}] "
                f"{event.type} | Score: {state.home_score}-{state.away_score}"
            )

            time.sleep(speed)
            
    def reset_match_state(self, match):
        state, _ = MatchState.objects.get_or_create(
            match=match,
            defaults={"status": match.status},
        )

        state.home_score = 0
        state.away_score = 0
        state.home_xg = 0
        state.away_xg = 0
        state.home_shots = 0
        state.away_shots = 0

        state.current_minute = 0
        state.current_second = 0
        state.period = 1
        state.status = match.status
        state.home_possession = 0
        state.away_possession = 0
        state.last_event = None

        state.save()
