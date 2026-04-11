"""Kafka consumer for live football match events."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction

from analytics.services.live_match_stats import GOAL_EVENT_TYPE, update_live_match_stats
from analytics.services.xg import calculate_shot_angle, calculate_shot_distance, calculate_xg
from analytics.services.xg.calculator import ShotFeatures
from core.consumers import broadcast_live_match_update
from core.models.event import Event
from core.models.match import Match
from core.models.player import Player
from core.models.shots import Shot
from core.models.substitution import Substitution
from core.models.team import Team

Pass = __import__("core.models.pass", fromlist=["Pass"]).Pass


logger = logging.getLogger(__name__)


class KafkaConsumerError(RuntimeError):
    """Raised when a Kafka match event cannot be consumed or processed."""


@dataclass(frozen=True)
class KafkaConsumerSettings:
    bootstrap_servers: str = "localhost:9092"
    topic: str = "match_events"
    group_id: str = "futball-live-event-writers"
    client_id: str = "futball-live-event-consumer"
    poll_timeout_seconds: float = 1.0
    auto_offset_reset: str = "earliest"


@dataclass(frozen=True)
class ProcessedEvent:
    event: Event
    created: bool
    detail_created: bool
    event_type: str


class MatchEventConsumer:
    """Consume live match events and store them in Django models."""

    def __init__(self, settings: KafkaConsumerSettings | None = None, **overrides):
        self.settings = settings or KafkaConsumerSettings(**overrides)
        self._consumer = self._build_consumer()
        self._running = False

    def run_forever(self) -> None:
        """Poll Kafka continuously and process messages one at a time."""
        self._consumer.subscribe([self.settings.topic])
        self._running = True

        try:
            while self._running:
                message = self._consumer.poll(self.settings.poll_timeout_seconds)
                if message is None:
                    continue

                if message.error():
                    raise KafkaConsumerError(str(message.error()))

                event = self._decode_message(message)
                result = process_match_event(event)
                self._consumer.commit(message=message, asynchronous=False)

                logger.info(
                    "Kafka match event processed",
                    extra={
                        "event_id": result.event.external_event_id,
                        "match_id": result.event.match_id,
                        "event_type": result.event_type,
                        "created": result.created,
                        "detail_created": result.detail_created,
                    },
                )
        finally:
            self.close()

    def stop(self) -> None:
        self._running = False

    def close(self) -> None:
        self._consumer.close()

    def _build_consumer(self):
        try:
            from confluent_kafka import Consumer
        except ImportError as exc:
            raise KafkaConsumerError(
                "confluent-kafka is required to consume match events. "
                "Install project dependencies before running the consumer."
            ) from exc

        return Consumer(
            {
                "bootstrap.servers": self.settings.bootstrap_servers,
                "group.id": self.settings.group_id,
                "client.id": self.settings.client_id,
                "enable.auto.commit": False,
                "auto.offset.reset": self.settings.auto_offset_reset,
                "isolation.level": "read_committed",
                "max.poll.interval.ms": 300000,
                "session.timeout.ms": 45000,
                "heartbeat.interval.ms": 15000,
            }
        )

    @staticmethod
    def _decode_message(message) -> dict[str, Any]:
        try:
            event = json.loads(message.value().decode("utf-8"))
        except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise KafkaConsumerError(f"Invalid Kafka event payload: {exc}") from exc

        if not isinstance(event, dict):
            raise KafkaConsumerError("Kafka event payload must decode to a JSON object")

        return event


@transaction.atomic
def process_match_event(event: dict[str, Any]) -> ProcessedEvent:
    """Persist one schema-compliant live match event idempotently."""
    _validate_event(event)

    event_type = event["event_type"]
    match = _resolve_match(event["match_id"])
    team = _resolve_team(event["team_id"], match)
    player = _resolve_player(event.get("player_id"), team, required=False)
    payload = event["payload"]

    try:
        event_row, created = Event.objects.get_or_create(
            external_event_id=str(event["event_id"]),
            defaults={
                "match": match,
                "period": int(event.get("period") or 1),
                "minute": int(event.get("minute") or 0),
                "second": int(event.get("second") or 0),
                "event_index": int(event.get("sequence") or 0),
                "possession": _safe_int(event.get("possession_id"), 0),
                "timestamp_ms": event.get("clock_ms"),
                "type": _map_event_type(event_type),
                "team": team,
                "player": player,
                "x": _event_x(event),
                "y": _event_y(event),
                "play_pattern": payload.get("play_pattern", ""),
                "extra_data": event,
            },
        )
    except IntegrityError:
        event_row = Event.objects.select_for_update().get(
            external_event_id=str(event["event_id"])
        )
        created = False

    if not created:
        return ProcessedEvent(
            event=event_row,
            created=False,
            detail_created=_has_detail(event_row, event_type),
            event_type=event_type,
        )

    detail_created = _create_event_detail(event_row, payload, event_type)
    update_live_match_stats(event_row)
    transaction.on_commit(lambda: broadcast_live_match_update(event_row))

    return ProcessedEvent(
        event=event_row,
        created=True,
        detail_created=detail_created,
        event_type=event_type,
    )


def _create_event_detail(event: Event, payload: dict[str, Any], event_type: str) -> bool:
    if event_type == Event.Type.PASS:
        return _create_pass(event, payload)
    if event_type == Event.Type.SHOT:
        return _create_shot(event, payload)
    if event_type == Event.Type.SUBSTITUTION:
        return _create_substitution(event, payload)
    return False


def _create_pass(event: Event, payload: dict[str, Any]) -> bool:
    if hasattr(event, "pass_detail"):
        return False

    end_location = payload.get("end_location") or {}
    recipient = _resolve_player(
        payload.get("recipient_player_id"),
        event.team,
        required=False,
    )

    Pass.objects.create(
        event=event,
        event_index=event.event_index,
        possession=event.possession,
        match=event.match,
        team=event.team,
        player=event.player,
        recipient=recipient,
        minute=event.minute,
        second=event.second,
        period=event.period,
        x=event.x,
        y=event.y,
        end_x=_scale_x(end_location.get("x")),
        end_y=_scale_y(end_location.get("y")),
        outcome=_choice(payload.get("outcome"), Pass.Outcome.values, Pass.Outcome.UNKNOWN),
        height=_choice(payload.get("height"), Pass.Height.values, Pass.Height.UNKNOWN),
        body_part=_choice(payload.get("body_part"), Pass.BodyPart.values, Pass.BodyPart.OTHER),
        pass_type=_choice(payload.get("pass_type"), Pass.PassType.values, Pass.PassType.UNKNOWN),
        play_pattern=payload.get("play_pattern", ""),
        under_pressure=bool(payload.get("under_pressure", False)),
        is_cross=bool(payload.get("is_cross", False)),
        is_cut_back=bool(payload.get("is_cutback", False)),
        is_switch=bool(payload.get("is_switch", False)),
        is_through_ball=bool(payload.get("is_through_ball", False)),
        shot_assist=bool(payload.get("shot_assist", False)),
        goal_assist=bool(payload.get("goal_assist", False)),
    )
    return True


def _create_shot(event: Event, payload: dict[str, Any]) -> bool:
    if hasattr(event, "shot_detail"):
        return False

    shot_type = _choice(
        payload.get("shot_type"),
        Shot.ShotType.values,
        Shot.ShotType.OPEN_PLAY,
    )
    body_part = _choice(payload.get("body_part"), Shot.BodyPart.values, Shot.BodyPart.OTHER)
    play_pattern = _choice(
        payload.get("play_pattern"),
        Shot.PlayPattern.values,
        Shot.PlayPattern.OPEN_PLAY,
    )
    xg = payload.get("xg")
    if xg is None:
        xg = calculate_xg(
            ShotFeatures(
                x=event.x,
                y=event.y,
                body_part=body_part,
                shot_type=shot_type,
                play_pattern=play_pattern,
                under_pressure=bool(payload.get("under_pressure", False)),
            )
        )
    else:
        xg = float(xg)

    assist_player = _resolve_player(
        payload.get("assist_player_id"),
        event.team,
        required=False,
    )

    Shot.objects.create(
        event=event,
        match=event.match,
        team=event.team,
        player=event.player,
        minute=event.minute,
        second=event.second,
        x=event.x,
        y=event.y,
        xg=xg,
        outcome=_choice(payload.get("outcome"), Shot.Outcome.values, Shot.Outcome.OFF_TARGET),
        is_goal=payload.get("outcome") == Shot.Outcome.GOAL,
        body_part=body_part,
        shot_type=shot_type,
        assist_player=assist_player,
        shot_angle=round(calculate_shot_angle(event.x, event.y), 4),
        shot_distance=round(calculate_shot_distance(event.x, event.y), 2),
        under_pressure=bool(payload.get("under_pressure", False)),
        play_pattern=play_pattern,
        is_big_chance=bool(payload.get("is_big_chance", xg >= 0.3)),
        period=event.period,
    )
    return True


def _create_substitution(event: Event, payload: dict[str, Any]) -> bool:
    if hasattr(event, "substitution_detail"):
        return False

    Substitution.objects.create(
        event=event,
        match=event.match,
        team=event.team,
        player_out=_resolve_player(payload.get("player_off_id"), event.team, required=False),
        player_in=_resolve_player(payload.get("player_on_id"), event.team, required=False),
        minute=event.minute,
        second=event.second,
        period=event.period,
        reason=payload.get("reason", ""),
    )
    return True


def _validate_event(event: dict[str, Any]) -> None:
    required = {
        "event_id",
        "event_type",
        "match_id",
        "team_id",
        "period",
        "minute",
        "second",
        "payload",
    }
    missing = sorted(field for field in required if field not in event)
    if missing:
        raise ValueError(f"Missing required event field(s): {', '.join(missing)}")
    if not isinstance(event["payload"], dict):
        raise ValueError("Event payload must be a JSON object")
    if event["event_type"] not in {
        Event.Type.PASS,
        Event.Type.SHOT,
        Event.Type.SUBSTITUTION,
        GOAL_EVENT_TYPE,
    }:
        raise ValueError(f"Unsupported event_type: {event['event_type']}")

    if event["event_type"] in {Event.Type.PASS, Event.Type.SHOT}:
        payload = event["payload"]
        location = payload.get("location") or payload.get("start_location") or {}
        if location.get("x") is None or location.get("y") is None:
            raise ValueError(f"{event['event_type']} event requires x/y coordinates")

    if event["event_type"] == Event.Type.PASS:
        end_location = event["payload"].get("end_location") or {}
        if end_location.get("x") is None or end_location.get("y") is None:
            raise ValueError("pass event requires end_location x/y coordinates")


def _resolve_match(value) -> Match:
    try:
        return _get_by_identity(Match, value)
    except Match.DoesNotExist as exc:
        raise ValueError(f"Match not found for id {value}") from exc


def _resolve_team(value, match: Match) -> Team:
    try:
        team = _get_by_identity(Team, value)
    except Team.DoesNotExist as exc:
        raise ValueError(f"Team not found for id {value}") from exc

    if team.id not in {match.home_team_id, match.away_team_id}:
        raise ValueError(f"Team {value} does not belong to match {match.id}")
    return team


def _resolve_player(value, team: Team, *, required: bool) -> Player | None:
    if value in {None, ""}:
        if required:
            raise ValueError("player_id is required")
        return None

    try:
        return _get_by_identity(Player, value)
    except Player.DoesNotExist:
        if required:
            raise ValueError(f"Player not found for id {value}")
        return None


def _get_by_identity(model, value):
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Expected numeric model identity, got {value!r}")

    try:
        return model.objects.get(id=numeric_value)
    except model.DoesNotExist:
        return model.objects.get(external_id=numeric_value)


def _map_event_type(value: str) -> str:
    if value == Event.Type.PASS:
        return Event.Type.PASS
    if value == Event.Type.SHOT:
        return Event.Type.SHOT
    if value == Event.Type.SUBSTITUTION:
        return Event.Type.SUBSTITUTION
    if value == GOAL_EVENT_TYPE:
        return GOAL_EVENT_TYPE
    raise ValueError(f"Unsupported event_type: {value}")


def _event_x(event: dict[str, Any]) -> float | None:
    payload = event["payload"]
    location = payload.get("location") or payload.get("start_location") or {}
    return _scale_x(location.get("x"))


def _event_y(event: dict[str, Any]) -> float | None:
    payload = event["payload"]
    location = payload.get("location") or payload.get("start_location") or {}
    return _scale_y(location.get("y"))


def _scale_x(value) -> float | None:
    return None if value is None else round(float(value) * 1.2, 2)


def _scale_y(value) -> float | None:
    return None if value is None else round(float(value) * 0.8, 2)


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _choice(value, valid_values, default):
    return value if value in valid_values else default


def _has_detail(event: Event, event_type: str) -> bool:
    if event_type == Event.Type.PASS:
        return hasattr(event, "pass_detail")
    if event_type == Event.Type.SHOT:
        return hasattr(event, "shot_detail")
    if event_type == Event.Type.SUBSTITUTION:
        return hasattr(event, "substitution_detail")
    return False
