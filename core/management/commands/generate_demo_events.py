"""Generate a realistic EVENT STREAM for development, not random aggregates.

Statistics must be derived from these events — never generated independently.
Uses the same EventCreateSerializer pipeline as the Live Match collection UI,
so derived metrics (xG, distances, progressive passes) and live stats stay
consistent with real collection.

Example:
    python manage.py generate_demo_events --match-id 1 --events 250 --seed 7
"""

import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.api.serializers import EventCreateSerializer
from core.models import Event, Match, Player


class Command(BaseCommand):
    help = "Generate a realistic sequential event stream for a match."

    def add_arguments(self, parser):
        parser.add_argument("--match-id", type=int, required=True)
        parser.add_argument("--events", type=int, default=250)
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing events for the match first.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        try:
            match = Match.objects.select_related("home_team", "away_team").get(
                pk=options["match_id"]
            )
        except Match.DoesNotExist:
            raise CommandError(f"Match {options['match_id']} does not exist.")

        squads = {
            match.home_team_id: list(
                Player.objects.filter(team_now_id=match.home_team_id).order_by("id")
            ),
            match.away_team_id: list(
                Player.objects.filter(team_now_id=match.away_team_id).order_by("id")
            ),
        }
        if not squads[match.home_team_id] or not squads[match.away_team_id]:
            raise CommandError("Both teams need at least one player for demo events.")

        if options["clear"]:
            Event.objects.filter(match=match).delete()
            self.stdout.write("Cleared existing events.")

        minute, second = 0, 12
        team_id = rng.choice([match.home_team_id, match.away_team_id])
        x, y = rng.uniform(20, 50), rng.uniform(25, 55)
        created = {"pass": 0, "shot": 0, "goal": 0, "save": 0, "other": 0}
        sub_minutes = sorted(rng.sample(range(55, 88), k=min(3, options["events"] // 80 or 1)))
        sub_done = 0

        total = options["events"]
        for i in range(total):
            second += rng.randint(5, 35)
            while second >= 60:
                second -= 60
                minute += 1
            minute = min(minute, 90)
            period = 1 if minute <= 45 else 2
            team_players = squads[team_id]
            player = rng.choice(team_players)

            roll = rng.random()
            if sub_done < len(sub_minutes) and minute >= sub_minutes[sub_done]:
                self._collect(match, {
                    "type": "substitution", "period": period,
                    "minute": minute, "second": second,
                    "team": team_id, "player": None, "x": x, "y": y,
                    "payload": {
                        "player_out_id": rng.choice(team_players).id,
                        "player_in_id": rng.choice(team_players).id,
                        "reason": "tactical",
                    },
                })
                sub_done += 1
                created["other"] += 1
                continue

            if roll < 0.78:
                # Pass: advance the ball, usually forward toward x=120.
                end_x = min(118, max(2, x + rng.uniform(-12, 22)))
                end_y = min(78, max(2, y + rng.uniform(-18, 18)))
                complete = rng.random() < 0.85
                recipient = None
                if complete:
                    candidates = [p for p in team_players if p.id != player.id]
                    recipient = rng.choice(candidates).id if candidates else None
                self._collect(match, {
                    "type": "pass", "period": period,
                    "minute": minute, "second": second,
                    "team": team_id, "player": player.id, "x": x, "y": y,
                    "payload": {
                        "end_x": round(end_x, 2), "end_y": round(end_y, 2),
                        "outcome": "complete" if complete else "incomplete",
                        "recipient_id": recipient,
                    },
                })
                created["pass"] += 1
                x, y = end_x, end_y
                if not complete or rng.random() < 0.12:
                    team_id = self._other_team(match, team_id)  # turnover
            elif roll < 0.84 and x > 75:
                # Shot: only from plausible attacking positions.
                outcome = rng.choices(
                    ["saved", "goal", "blocked", "off_target"],
                    weights=[0.40, 0.15, 0.15, 0.30],
                )[0]
                payload = {
                    "outcome": outcome,
                    "body_part": rng.choice(["right_foot", "left_foot", "head"]),
                }
                if outcome == "saved":
                    keepers = squads[self._other_team(match, team_id)]
                    payload["save_player_id"] = rng.choice(keepers).id
                    created["save"] += 1
                if outcome == "goal":
                    team_players_now = squads[team_id]
                    candidates = [p for p in team_players_now if p.id != player.id]
                    if candidates and rng.random() < 0.5:
                        payload["assist_player_id"] = rng.choice(candidates).id
                    created["goal"] += 1
                self._collect(match, {
                    "type": "goal" if outcome == "goal" else "shot",
                    "period": period, "minute": minute, "second": second,
                    "team": team_id, "player": player.id, "x": x, "y": y,
                    "payload": payload,
                })
                created["shot"] += 1
                # After a shot the other team restarts: keeper/long ball.
                team_id = self._other_team(match, team_id)
                x, y = rng.uniform(10, 30), rng.uniform(25, 55)
            elif roll < 0.90:
                self._collect(match, {
                    "type": "duel", "period": period,
                    "minute": minute, "second": second,
                    "team": team_id, "player": player.id, "x": x, "y": y,
                    "payload": {},
                })
                created["other"] += 1
                if rng.random() < 0.5:
                    team_id = self._other_team(match, team_id)
            elif roll < 0.95:
                self._collect(match, {
                    "type": "foul", "period": period,
                    "minute": minute, "second": second,
                    "team": team_id, "player": player.id, "x": x, "y": y,
                    "payload": {},
                })
                created["other"] += 1
                if rng.random() < 0.18:
                    self._collect(match, {
                        "type": "card", "period": period,
                        "minute": minute, "second": second,
                        "team": team_id, "player": player.id, "x": x, "y": y,
                        "payload": {"card": "yellow"},
                    })
                    created["other"] += 1
                team_id = self._other_team(match, team_id)
            else:
                # Loose ball drifts; possession flips nearby.
                team_id = self._other_team(match, team_id)
                x = min(118, max(2, x + rng.uniform(-15, 15)))
                y = min(78, max(2, y + rng.uniform(-15, 15)))
                self._collect(match, {
                    "type": "duel", "period": period,
                    "minute": minute, "second": second,
                    "team": team_id,
                    "player": rng.choice(squads[team_id]).id,
                    "x": x, "y": y, "payload": {},
                })
                created["other"] += 1

        self.stdout.write(self.style.SUCCESS(
            f"Generated event stream for match {match.pk}: "
            f"{created['pass']} passes, {created['shot']} shots "
            f"({created['goal']} goals, {created['save']} saves), "
            f"{created['other']} other events. Aggregates derived from events."
        ))

    def _collect(self, match, data):
        serializer = EventCreateSerializer(data=data, context={"match": match})
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    @staticmethod
    def _other_team(match, team_id):
        return (
            match.away_team_id if team_id == match.home_team_id else match.home_team_id
        )
