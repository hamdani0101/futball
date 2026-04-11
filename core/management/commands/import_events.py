"""Management command to import shots."""

import json
from pathlib import Path
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand

from analytics.services.xg import (
    calculate_shot_angle,
    calculate_shot_distance,
    calculate_xg,
    features_from_statsbomb_event,
)
from core.models import Match, MatchState, Player, Pass, Event, Shot

PASS_OUTCOME_MAP = {
    "Incomplete": Pass.Outcome.INCOMPLETE,
    "Out": Pass.Outcome.OUT,
    "Pass Offside": Pass.Outcome.OFFSIDE,
}

PASS_HEIGHT_MAP = {
    "Ground Pass": Pass.Height.GROUND,
    "Low Pass": Pass.Height.LOW,
    "High Pass": Pass.Height.HIGH,
}

PASS_BODY_PART_MAP = {
    "Right Foot": Pass.BodyPart.RIGHT_FOOT,
    "Left Foot": Pass.BodyPart.LEFT_FOOT,
    "Head": Pass.BodyPart.HEAD,
    "Chest": Pass.BodyPart.CHEST,
}

PASS_TECHNIQUE_MAP = {
    "Backheel": Pass.Technique.BACKHEEL,
    "Half Volley": Pass.Technique.HALF_VOLLEY,
    "Lob": Pass.Technique.LOB,
    "Normal": Pass.Technique.NORMAL,
    "Overhead Kick": Pass.Technique.OVERHEAD,
    "Volley": Pass.Technique.VOLLEY,
}

PASS_TYPE_MAP = {
    "Corner": Pass.PassType.CORNER,
    "Free Kick": Pass.PassType.FREE_KICK,
    "Goal Kick": Pass.PassType.GOAL_KICK,
    "Kick Off": Pass.PassType.KICK_OFF,
    "Open Play": Pass.PassType.OPEN_PLAY,
    "Recovery": Pass.PassType.RECOVERY,
    "Throw-in": Pass.PassType.THROW_IN,
}

SHOT_OUTCOME_MAP = {
    "Goal": Shot.Outcome.GOAL,
    "Saved": Shot.Outcome.SAVED,
    "Saved Off Target": Shot.Outcome.SAVED,
    "Blocked": Shot.Outcome.BLOCKED,
    "Off T": Shot.Outcome.OFF_TARGET,
    "Off Target": Shot.Outcome.OFF_TARGET,
    "Wayward": Shot.Outcome.OFF_TARGET,
    "Post": Shot.Outcome.OFF_TARGET,
}

SHOT_BODY_PART_MAP = {
    "Right Foot": Shot.BodyPart.RIGHT_FOOT,
    "Left Foot": Shot.BodyPart.LEFT_FOOT,
    "Head": Shot.BodyPart.HEAD,
}

SHOT_TYPE_MAP = {
    "Open Play": Shot.ShotType.OPEN_PLAY,
    "Penalty": Shot.ShotType.PENALTY,
    "Free Kick": Shot.ShotType.FREE_KICK,
}

SHOT_PLAY_PATTERN_MAP = {
    "Open Play": Shot.PlayPattern.OPEN_PLAY,
    "From Corner": Shot.PlayPattern.CORNER,
    "From Free Kick": Shot.PlayPattern.FREE_KICK,
    "From Keeper": Shot.PlayPattern.OPEN_PLAY,
    "From Kick Off": Shot.PlayPattern.OPEN_PLAY,
    "From Throw In": Shot.PlayPattern.OPEN_PLAY,
    "Regular Play": Shot.PlayPattern.OPEN_PLAY,
}


class Command(BaseCommand):
    help = "Import StatsBomb shot-by-shot events from JSON files"

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            nargs="?",
            type=str,
            default="",
            help=(
                "File or directory containing StatsBomb event JSON files. "
                "Defaults to STATSBOMB_DATA_DIR/events."
            ),
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete existing shots for a match before importing",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report counts without writing to the DB",
        )

    def handle(self, *args, **options):
        input_path = Path(options["path"] or settings.STATSBOMB_DATA_DIR / "events")
        replace = options["replace"]
        dry_run = options["dry_run"]

        if not input_path.exists():
            self.stderr.write(
                self.style.ERROR(f"Path not found: {input_path}")
            )
            return

        files = self.collect_files(input_path)
        if not files:
            self.stderr.write(
                self.style.ERROR("No JSON files found.")
            )
            return

        total_created = total_skipped = total_events = 0

        for file_path in files:
            created, skipped, events = self.import_file(
                file_path=file_path,
                replace=replace,
                dry_run=dry_run,
            )
            total_created += created
            total_skipped += skipped
            total_events += events

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: {total_events} shots scanned, "
                    f"{total_created} would be created, "
                    f"{total_skipped} skipped."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {total_events} shots scanned, "
                f"{total_created} created, "
                f"{total_skipped} skipped."
            )
        )

    # --------------------
    # Helpers
    # --------------------

    @staticmethod
    def collect_files(input_path: Path):
        if input_path.is_file():
            return [input_path] if input_path.suffix == ".json" else []

        files = sorted(input_path.rglob("*.json"))
        return [
            f for f in files
            if f.name not in {"matches.json", "competitions.json"}
        ]

    def import_file(self, file_path, replace, dry_run):
        statsbomb_id = file_path.stem
        match = Match.objects.filter(external_id=statsbomb_id).first()
        if not match:
            self.stdout.write(
                self.style.WARNING(
                    f"Skip {file_path.name}: no Match with match_id={statsbomb_id}"
                )
            )
            return 0, 0, 0

        with open(file_path, encoding="utf-8") as f:
            events = json.load(f)

        if not isinstance(events, list):
            self.stdout.write(
                self.style.WARNING(
                    f"Skip {file_path.name}: JSON is not a list of events"
                )
            )
            return 0, 0, 0
        
        skipped = 0
        stats_by_team = defaultdict(lambda: {
            "xg": 0.0,
            "shots": 0,
            "shots_on_target": 0,
            "penalties": 0
        })

        skipped = 0
        prev_event_obj = None

        for raw in events:
            event_type = (raw.get("type") or {}).get("name")

            team_id = (raw.get("team") or {}).get("id")
            team = self.resolve_team(match, team_id)
            if not team:
                skipped += 1
                continue

            # PLAYER
            player = None
            player_payload = raw.get("player") or {}
            if player_payload.get("id"):
                player, _ = Player.objects.get_or_create(
                    external_id=player_payload["id"],
                    defaults={
                        "name": player_payload.get("name", "Unknown"),
                        "team_now": team,
                    },
                )

            # 🔥 CREATE EVENT (SELALU)
            event_obj = self.create_event(raw, match, team, player)

            if event_type == "Shot":
                self.create_shot(event_obj, raw, prev_event_obj, stats_by_team)

            elif event_type == "Pass":
                self.create_pass(event_obj, raw)

            prev_event_obj = event_obj
            
            
        self.stdout.write(
            self.style.SUCCESS(
                f"{file_path.name}: {len(stats_by_team)} imported, {skipped} skipped"
            )
        )
        
        created = Event.objects.filter(match=match).count()
        return created, skipped, len(events)
    
    def create_shot(self, event_obj, raw, prev_event_obj, stats_by_team):
        shot_payload = raw.get("shot") or {}

        outcome_name = (shot_payload.get("outcome") or {}).get("name", "")
        outcome = SHOT_OUTCOME_MAP.get(outcome_name, Shot.Outcome.OFF_TARGET)

        shot_features = features_from_statsbomb_event(raw)
        xg = self.get_shot_xg(shot_payload, shot_features)

        assist_player = None
        if prev_event_obj and prev_event_obj.type == "pass":
            assist_player = prev_event_obj.player

        Shot.objects.create(
            event=event_obj,
            match=event_obj.match,
            team=event_obj.team,
            player=event_obj.player,

            minute=event_obj.minute,
            second=event_obj.second,

            x=event_obj.x,
            y=event_obj.y,
            xg=xg,

            outcome=outcome,
            is_goal=outcome == Shot.Outcome.GOAL,

            assist_player=assist_player,

            play_pattern=SHOT_PLAY_PATTERN_MAP.get(
                (raw.get("play_pattern") or {}).get("name"),
                Shot.PlayPattern.OPEN_PLAY,
            ),
            is_big_chance=xg >= 0.3,
            under_pressure=raw.get("under_pressure", False),
            body_part=SHOT_BODY_PART_MAP.get(
                (shot_payload.get("body_part") or {}).get("name"),
                Shot.BodyPart.OTHER,
            ),
            shot_type=SHOT_TYPE_MAP.get(
                (shot_payload.get("type") or {}).get("name"),
                Shot.ShotType.OPEN_PLAY,
            ),
            shot_distance=round(calculate_shot_distance(event_obj.x, event_obj.y), 2),
            shot_angle=round(calculate_shot_angle(event_obj.x, event_obj.y), 4),
            period=event_obj.period,
        )

        stats_by_team[event_obj.team]["xg"] += xg
        stats_by_team[event_obj.team]["shots"] += 1
            
    def create_pass(self, event_obj, raw):
        p = raw.get("pass") or {}

        end = p.get("end_location") or [None, None]

        recipient = None
        recipient_payload = p.get("recipient") or {}
        if recipient_payload.get("id"):
            recipient, _ = Player.objects.get_or_create(
                external_id=recipient_payload["id"],
                defaults={"name": recipient_payload.get("name", "Unknown")},
            )

        Pass.objects.create(
            event=event_obj,
            event_index=event_obj.event_index,
            possession=event_obj.possession,
            match=event_obj.match,
            team=event_obj.team,
            player=event_obj.player,
            recipient=recipient,

            minute=event_obj.minute,
            second=event_obj.second,
            period=event_obj.period,

            x=event_obj.x,
            y=event_obj.y,
            end_x=end[0],
            end_y=end[1],

            length=self.to_float(p.get("length")),
            angle=self.to_float(p.get("angle")),

            outcome=self.map_outcome(p),
            height=self.map_height(p),
            body_part=self.map_body_part(p),
            technique=self.map_technique(p),
            pass_type=self.map_pass_type(p),

            play_pattern=(raw.get("play_pattern") or {}).get("name"),

            under_pressure=raw.get("under_pressure", False),

            is_cross=p.get("cross", False),
            is_cut_back=p.get("cut_back", False),
            is_switch=p.get("switch", False),
            is_through_ball=p.get("through_ball", False),

            shot_assist=p.get("shot_assist", False),
            goal_assist=p.get("goal_assist", False),
        )

    def resolve_team(self, match, team_id):
        if not team_id:
            return match.home_team  # fallback aman

        if match.home_team.external_id == team_id:
            return match.home_team

        if match.away_team.external_id == team_id:
            return match.away_team

        # fallback terakhir (optional)
        return match.home_team

    def get_player_by_name(self, name):
        return Player.objects.filter(name=name).first()
    
    def update_match_state(self, event_obj):
        state, _ = MatchState.objects.get_or_create(
            match=event_obj.match,
            defaults={"status": event_obj.match.status},
        )

        state.current_minute = event_obj.minute
        state.current_second = event_obj.second
        state.period = event_obj.period
        state.status = event_obj.match.status

        state.last_event = event_obj
        state.save()

    def create_event(self, raw, match, team, player):
        location = raw.get("location") or [None, None]

        return Event.objects.create(
            external_event_id=raw.get("id"),
            match=match,
            period=raw.get("period"),
            minute=int(raw.get("minute") or 0),
            second=int(raw.get("second") or 0),
            timestamp_ms=self.generate_timestamp(raw),
            event_index=raw.get("index"),
            possession=int(raw.get("possession") or 0),

            type=self.map_event_type(raw),

            team=team,
            player=player,

            x=float(location[0]) if location[0] is not None else None,
            y=float(location[1]) if location[1] is not None else None,

            extra_data=raw,
        )
        
    def map_event_type(self, raw):
        t = (raw.get("type") or {}).get("name", "")

        if t == "Shot":
            return "shot"
        elif t == "Pass":
            return "pass"
        elif t == "Foul Committed":
            return "foul"
        elif t == "Substitution":
            return "sub"
        return "other"


    def generate_timestamp(self, raw):
        minute = int(raw.get("minute") or 0)
        second = int(raw.get("second") or 0)
        return minute * 60000 + second * 1000
    
    @staticmethod
    def to_float(value):
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def map_outcome(pass_payload):
        outcome_name = (pass_payload.get("outcome") or {}).get("name")
        if not outcome_name:
            return Pass.Outcome.COMPLETE
        return PASS_OUTCOME_MAP.get(outcome_name, Pass.Outcome.UNKNOWN)

    @staticmethod
    def map_height(pass_payload):
        height_name = (pass_payload.get("height") or {}).get("name")
        return PASS_HEIGHT_MAP.get(height_name, Pass.Height.UNKNOWN)

    @staticmethod
    def map_body_part(pass_payload):
        body_part_name = (pass_payload.get("body_part") or {}).get("name")
        return PASS_BODY_PART_MAP.get(body_part_name, Pass.BodyPart.OTHER if body_part_name else "")

    @staticmethod
    def map_technique(pass_payload):
        technique_name = (pass_payload.get("technique") or {}).get("name")
        if not technique_name:
            return ""
        return PASS_TECHNIQUE_MAP.get(technique_name, Pass.Technique.UNKNOWN)

    @staticmethod
    def map_pass_type(pass_payload):
        pass_type_name = (pass_payload.get("type") or {}).get("name")
        if not pass_type_name:
            return Pass.PassType.OPEN_PLAY
        return PASS_TYPE_MAP.get(pass_type_name, Pass.PassType.UNKNOWN)

    @staticmethod
    def clamp(value, low, high):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return max(low, min(high, value))

    @staticmethod
    def get_shot_xg(shot_payload, shot_features):
        provider_xg = shot_payload.get("statsbomb_xg")
        if provider_xg is not None:
            try:
                return float(provider_xg)
            except (TypeError, ValueError):
                pass

        return calculate_xg(shot_features)
