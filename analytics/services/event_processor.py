"""Service-layer event normalization and live match-stat updates."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from analytics.services.xg.calculator import ShotFeatures, calculate_xg
from core.models.event import Event
from core.models.match import Match
from core.models.match_team_stat import MatchTeamStats


logger = logging.getLogger(__name__)


SUPPORTED_EVENT_TYPES = {
    Event.Type.PASS,
    Event.Type.SHOT,
    Event.Type.SUBSTITUTION,
}
ON_TARGET_OUTCOMES = {"goal", "saved", "saved_off_target"}


@dataclass(frozen=True)
class NormalizedEvent:
    """Canonical event representation used by the processor."""

    event_type: str
    match_id: int | None
    team_id: int | None
    player_id: int | None
    minute: int
    second: int
    period: int
    x: float | None
    y: float | None
    outcome: str
    xg: float | None
    raw_event: Any


@dataclass(frozen=True)
class LiveStatsSnapshot:
    """Small response payload describing the current team live stats."""

    match_id: int
    team_id: int
    possession: int
    xg: float
    passes: int
    completed_passes: int
    pass_accuracy: float
    shots: int
    shots_on_target: int
    goals: int


@dataclass(frozen=True)
class ProcessedEventResult:
    """Outcome returned by the event processor."""

    normalized_event: NormalizedEvent
    stats: LiveStatsSnapshot | None
    skipped: bool = False
    reason: str = ""


class EventProcessor:
    """Normalize incoming events and update match statistics."""

    def __init__(self, logger_instance: logging.Logger | None = None):
        self.logger = logger_instance or logger
        self._last_event_by_match: dict[int, NormalizedEvent] = {}

    def process_event(self, event: Any) -> ProcessedEventResult:
        """Normalize and process a single match event."""
        normalized_event = self._normalize_event(event)

        if normalized_event.event_type not in SUPPORTED_EVENT_TYPES:
            self.logger.info(
                "Skipping unsupported live event type",
                extra={
                    "event_type": normalized_event.event_type,
                    "match_id": normalized_event.match_id,
                    "team_id": normalized_event.team_id,
                },
            )
            return ProcessedEventResult(
                normalized_event=normalized_event,
                stats=None,
                skipped=True,
                reason=f"Unsupported event type: {normalized_event.event_type}",
            )

        stats = self.update_live_stats(normalized_event)

        self.logger.info(
            "Live event processed",
            extra={
                "event_type": normalized_event.event_type,
                "match_id": normalized_event.match_id,
                "team_id": normalized_event.team_id,
                "minute": normalized_event.minute,
            },
        )
        return ProcessedEventResult(normalized_event=normalized_event, stats=stats)

    @transaction.atomic
    def update_live_stats(
        self,
        event: NormalizedEvent | dict[str, Any] | Event,
    ) -> LiveStatsSnapshot | None:
        """Update live team stats for one normalized event."""
        normalized_event = (
            event if isinstance(event, NormalizedEvent) else self._normalize_event(event)
        )

        if normalized_event.match_id is None or normalized_event.team_id is None:
            self.logger.warning(
                "Live stats update skipped because match/team context is missing",
                extra={
                    "event_type": normalized_event.event_type,
                    "match_id": normalized_event.match_id,
                    "team_id": normalized_event.team_id,
                },
            )
            return None

        match = Match.objects.select_for_update().get(pk=normalized_event.match_id)
        stats, _ = MatchTeamStats.objects.select_for_update().get_or_create(
            match=match,
            team_id=normalized_event.team_id,
        )

        self._update_match_clock(match, normalized_event)
        self._allocate_possession(match, normalized_event)
        self._apply_event_effects(stats, normalized_event)
        self._update_last_event_reference(stats, normalized_event.raw_event)
        stats.save()

        self._refresh_derived_stats(match.id)
        stats.refresh_from_db()
        self._remember_last_event(normalized_event)

        return LiveStatsSnapshot(
            match_id=stats.match_id,
            team_id=stats.team_id,
            possession=int(stats.possession),
            xg=round(float(stats.xg or 0.0), 4),
            passes=int(stats.passes),
            completed_passes=int(stats.completed_passes),
            pass_accuracy=round(float(stats.pass_accuracy or 0.0), 2),
            shots=int(stats.shots),
            shots_on_target=int(stats.shots_on_target),
            goals=int(stats.goals),
        )

    def _normalize_event(self, event: Any) -> NormalizedEvent:
        if isinstance(event, Event):
            return self._normalize_model_event(event)
        if isinstance(event, dict):
            return self._normalize_dict_event(event)
        raise TypeError(f"Unsupported event payload: {type(event)!r}")

    def _normalize_model_event(self, event: Event) -> NormalizedEvent:
        shot_detail = self._related_or_none(event, "shot_detail")
        pass_detail = self._related_or_none(event, "pass_detail")

        outcome = ""
        xg = None
        if shot_detail is not None:
            outcome = shot_detail.outcome or ""
            xg = float(shot_detail.xg or 0.0)
        elif pass_detail is not None:
            outcome = pass_detail.outcome or ""

        return NormalizedEvent(
            event_type=(event.type or "").lower(),
            match_id=event.match_id,
            team_id=event.team_id,
            player_id=event.player_id,
            minute=int(event.minute or 0),
            second=int(event.second or 0),
            period=int(event.period or 1),
            x=self._safe_float(event.x),
            y=self._safe_float(event.y),
            outcome=outcome.lower(),
            xg=xg,
            raw_event=event,
        )

    def _normalize_dict_event(self, event: dict[str, Any]) -> NormalizedEvent:
        payload = event.get("payload") or {}
        location = payload.get("location") or payload.get("start_location") or {}

        event_type = str(event.get("type") or event.get("event_type") or "").lower()
        x = self._safe_float(event.get("x"), allow_none=True)
        y = self._safe_float(event.get("y"), allow_none=True)
        if x is None:
            x = self._safe_float(location.get("x"), allow_none=True)
        if y is None:
            y = self._safe_float(location.get("y"), allow_none=True)

        xg = self._safe_float(payload.get("xg"), allow_none=True)
        if xg is None and event_type == Event.Type.SHOT and x is not None and y is not None:
            xg = calculate_xg(ShotFeatures(x=x, y=y))

        return NormalizedEvent(
            event_type=event_type,
            match_id=self._safe_int(event.get("match_id"), allow_none=True),
            team_id=self._safe_int(event.get("team_id"), allow_none=True),
            player_id=self._safe_int(event.get("player_id"), allow_none=True),
            minute=self._safe_int(event.get("minute"), default=0),
            second=self._safe_int(event.get("second"), default=0),
            period=self._safe_int(event.get("period"), default=1),
            x=x,
            y=y,
            outcome=str(payload.get("outcome") or event.get("outcome") or "").lower(),
            xg=xg,
            raw_event=event,
        )

    def _update_match_clock(self, match: Match, event: NormalizedEvent) -> None:
        match.current_minute = event.minute
        match.current_second = event.second
        match.period = event.period
        match.save(update_fields=["current_minute", "current_second", "period", "updated_at"])

    def _allocate_possession(self, match: Match, event: NormalizedEvent) -> None:
        previous_event = self._get_previous_event(match.id)
        if previous_event is None or previous_event.team_id is None:
            return

        delta_seconds = self._event_seconds(event) - self._event_seconds(previous_event)
        if delta_seconds <= 0 or delta_seconds > 180:
            return

        previous_stats, _ = MatchTeamStats.objects.select_for_update().get_or_create(
            match=match,
            team_id=previous_event.team_id,
        )
        previous_stats.possession_seconds += delta_seconds
        previous_stats.save(update_fields=["possession_seconds", "updated_at"])

    def _apply_event_effects(self, stats: MatchTeamStats, event: NormalizedEvent) -> None:
        if event.event_type == Event.Type.PASS:
            stats.passes += 1
            if event.outcome in {"", "complete"}:
                stats.completed_passes += 1
            return

        if event.event_type == Event.Type.SHOT:
            stats.shots += 1
            stats.xg += float(event.xg or 0.0)
            if event.outcome in ON_TARGET_OUTCOMES:
                stats.shots_on_target += 1
            if event.outcome == "goal":
                stats.goals += 1
            return

        if event.event_type == Event.Type.SUBSTITUTION:
            # Substitutions only advance the clock and possession windows.
            return

    def _update_last_event_reference(self, stats: MatchTeamStats, raw_event: Any) -> None:
        if isinstance(raw_event, Event):
            stats.last_event = raw_event

    def _refresh_derived_stats(self, match_id: int) -> None:
        rows = list(
            MatchTeamStats.objects.select_for_update().filter(match_id=match_id)
        )
        total_possession_seconds = sum(float(row.possession_seconds or 0.0) for row in rows)

        for row in rows:
            row.pass_accuracy = round(
                (row.completed_passes / row.passes) * 100,
                2,
            ) if row.passes else 0.0
            row.possession = round(
                (row.possession_seconds / total_possession_seconds) * 100
            ) if total_possession_seconds else 0
            row.save(update_fields=["pass_accuracy", "possession", "updated_at"])

    def _event_seconds(self, event: NormalizedEvent) -> int:
        return (event.minute * 60) + event.second

    def _get_previous_event(self, match_id: int) -> NormalizedEvent | None:
        cached_event = self._last_event_by_match.get(match_id)
        if cached_event is not None:
            return cached_event

        previous_stats = (
            MatchTeamStats.objects.select_for_update()
            .filter(match_id=match_id, last_event__isnull=False)
            .exclude(last_event__team_id__isnull=True)
            .order_by("-last_event__period", "-last_event__minute", "-last_event__second", "-id")
            .first()
        )
        if previous_stats is None or previous_stats.last_event is None:
            return None
        return self._normalize_model_event(previous_stats.last_event)

    def _remember_last_event(self, event: NormalizedEvent) -> None:
        if event.match_id is not None:
            self._last_event_by_match[event.match_id] = event

    def _related_or_none(self, instance: Any, attribute: str) -> Any:
        try:
            return getattr(instance, attribute)
        except (AttributeError, ObjectDoesNotExist):
            return None

    def _safe_int(
        self,
        value: Any,
        default: int | None = None,
        *,
        allow_none: bool = False,
    ) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None if allow_none else default

    def _safe_float(self, value: Any, *, allow_none: bool = False) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None if allow_none else 0.0


def process_event(event: Any) -> ProcessedEventResult:
    """Compatibility wrapper for callers expecting a module-level function."""
    return EventProcessor().process_event(event)
