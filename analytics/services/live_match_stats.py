"""Incremental live match-stat updates from incoming football events."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.db.models import F

from core.models.event import Event
from core.models.match_team_stat import MatchTeamStats
from core.models.shots import Shot

Pass = __import__("core.models.pass", fromlist=["Pass"]).Pass


GOAL_EVENT_TYPE = "goal"
ON_TARGET_SHOT_OUTCOMES = {Shot.Outcome.GOAL, Shot.Outcome.SAVED}


@dataclass(frozen=True)
class LiveMatchStatsSnapshot:
    match_id: int
    team_id: int
    possession: int
    total_shots: int
    xg: float
    pass_accuracy: float


COUNTER_FIELDS = (
    "passes",
    "completed_passes",
    "shots",
    "shots_on_target",
    "goals",
)


def _event_counter_deltas(event: Event) -> dict:
    """Pure per-event counter increments (xg carried separately as float).

    Single canonical definition of what one event contributes, shared by the
    live incremental path and the batch rebuild. Semantics preserved exactly:

    - passes/completed from the pass detail outcome;
    - shots/xG/on-target/goals from the shot detail outcome;
    - a goal counts its shot, on-target and xG exactly once via its own
      shot_detail; bare goal rows without one contribute only the goal.
    """
    deltas = {field: 0 for field in COUNTER_FIELDS}
    xg = 0.0

    if event.type == Event.Type.PASS:
        pass_detail = getattr(event, "pass_detail", None)
        if pass_detail is not None:
            deltas["passes"] = 1
            if pass_detail.outcome == Pass.Outcome.COMPLETE:
                deltas["completed_passes"] = 1
    elif event.type == Event.Type.SHOT:
        shot_detail = getattr(event, "shot_detail", None)
        if shot_detail is not None:
            deltas["shots"] = 1
            xg = float(shot_detail.xg or 0)
            if shot_detail.outcome in ON_TARGET_SHOT_OUTCOMES:
                deltas["shots_on_target"] = 1
            if shot_detail.outcome == Shot.Outcome.GOAL:
                deltas["goals"] = 1
    elif event.type == GOAL_EVENT_TYPE:
        shot_detail = getattr(event, "shot_detail", None)
        if shot_detail is not None:
            deltas["shots"] = 1
            xg = float(shot_detail.xg or 0)
            deltas["shots_on_target"] = 1
        deltas["goals"] = 1

    deltas["xg"] = xg
    return deltas


def _f_expressions(deltas: dict) -> dict:
    """Translate nonzero counter deltas (plus xG) into F() increments."""
    expressions = {}
    for field in COUNTER_FIELDS:
        if deltas[field]:
            expressions[field] = F(field) + deltas[field]
    if deltas["xg"]:
        expressions["xg"] = F("xg") + deltas["xg"]
    return expressions


def _possession_transfer(event: Event, previous_event) -> tuple | None:
    """Pure possession rule shared by both paths.

    Returns (team_id, delta_seconds) credited to the *previous* event's team,
    or None when the gap is outside the (0, 180] second window or the
    previous event has no team. Replicates the live rule exactly, including
    that only the latest key-pair ever allocates during a rebuild (the
    predecessor query takes the global max excluding self).
    """
    if previous_event is None or not previous_event.team_id:
        return None
    delta_seconds = _event_seconds(event) - _event_seconds(previous_event)
    if delta_seconds <= 0 or delta_seconds > 180:
        return None
    return previous_event.team_id, delta_seconds


@transaction.atomic
def update_live_match_stats(event: Event) -> LiveMatchStatsSnapshot:
    """Incrementally update match stats for a newly persisted event."""
    _allocate_possession_time(event)

    stats, _ = MatchTeamStats.objects.select_for_update().get_or_create(
        match=event.match,
        team=event.team,
    )

    update_fields = {"last_event": event}
    update_fields.update(_f_expressions(_event_counter_deltas(event)))

    MatchTeamStats.objects.filter(pk=stats.pk).update(**update_fields)
    _refresh_derived_match_rates(event.match_id)

    stats.refresh_from_db()
    return LiveMatchStatsSnapshot(
        match_id=stats.match_id,
        team_id=stats.team_id,
        possession=stats.possession,
        total_shots=stats.shots,
        xg=round(stats.xg, 4),
        pass_accuracy=round(stats.pass_accuracy, 2),
    )


@transaction.atomic
def rebuild_match_aggregates(match_id: int) -> None:
    """Rebuild one match's aggregates from its event stream (batch).

    Match-scoped only (indexed ``match_id`` filter); never touches other
    matches. Used after edits and deletions so derived totals can't go stale.

    The complete sequence is loaded once in canonical order, predecessor and
    possession information are derived in Python in a single pass, and team
    rows are written back with one bulk update — O(n) queries instead of
    O(n) predecessor filesorts. Every rule (counter deltas, possession
    window, rate formulas) is the shared pure helper also used by the live
    path, so output is identical to replaying ``update_live_match_stats``.
    """
    from analytics.services.live_dashboard import invalidate_live_stats_cache

    invalidate_live_stats_cache(match_id)
    MatchTeamStats.objects.filter(match_id=match_id).update(
        shots=0,
        shots_on_target=0,
        xg=0.0,
        passes=0,
        completed_passes=0,
        pass_accuracy=0.0,
        goals=0,
        possession=0,
        possession_seconds=0.0,
    )
    events = list(
        Event.objects.filter(match_id=match_id)
        .select_related("team")
        .prefetch_related("shot_detail", "pass_detail")
        .order_by("period", "minute", "second", "event_index", "id")
    )
    if not events:
        return

    rows = {
        row.team_id: row
        for row in MatchTeamStats.objects.select_for_update().filter(
            match_id=match_id
        )
    }
    missing = {event.team_id for event in events} - rows.keys()
    if missing:
        MatchTeamStats.objects.bulk_create(
            [MatchTeamStats(match_id=match_id, team_id=team_id) for team_id in missing]
        )
        rows.update(
            {
                row.team_id: row
                for row in MatchTeamStats.objects.select_for_update().filter(
                    match_id=match_id, team_id__in=missing
                )
            }
        )

    totals = {
        team_id: {
            "passes": 0,
            "completed_passes": 0,
            "shots": 0,
            "shots_on_target": 0,
            "goals": 0,
            "xg": 0.0,
            "possession_seconds": 0.0,
        }
        for team_id in rows
    }
    last_event_ids: dict = {}

    # Replicates the predecessor query (.exclude(pk).order_by(-period,
    # -timestamp_ms, -event_index, -id).first()): the global maximum key
    # excluding self. MySQL sorts NULL timestamps lowest, so they rank last
    # under DESC — hence negative infinity here. Ids are unique, so keys are
    # always distinct and the top two fully determine every predecessor.
    latest = second_latest = None
    latest_key = second_key = None
    for event in events:
        key = _predecessor_key(event)
        if latest_key is None or key > latest_key:
            second_latest, second_key = latest, latest_key
            latest, latest_key = event, key
        elif second_key is None or key > second_key:
            second_latest, second_key = event, key

    for event in events:
        deltas = _event_counter_deltas(event)
        team_totals = totals[event.team_id]
        for field in COUNTER_FIELDS:
            team_totals[field] += deltas[field]
        team_totals["xg"] += deltas["xg"]
        last_event_ids[event.team_id] = event.pk

        previous = second_latest if event is latest else latest
        transfer = _possession_transfer(event, previous)
        if transfer is not None:
            # The previous event is always part of this match's stream, so
            # its team row was ensured above.
            transfer_team_id, delta_seconds = transfer
            totals[transfer_team_id]["possession_seconds"] += delta_seconds

    total_possession_seconds = sum(
        team_totals["possession_seconds"] for team_totals in totals.values()
    )
    for team_id, row in rows.items():
        team_totals = totals[team_id]
        row.passes = team_totals["passes"]
        row.completed_passes = team_totals["completed_passes"]
        row.shots = team_totals["shots"]
        row.shots_on_target = team_totals["shots_on_target"]
        row.goals = team_totals["goals"]
        row.xg = team_totals["xg"]
        row.possession_seconds = team_totals["possession_seconds"]
        # Same formulas as _refresh_derived_match_rates (round() identical).
        row.possession = (
            round((row.possession_seconds / total_possession_seconds) * 100)
            if total_possession_seconds
            else 0
        )
        row.pass_accuracy = (
            round((row.completed_passes / row.passes) * 100, 2)
            if row.passes
            else 0.0
        )
        if team_id in last_event_ids:
            row.last_event_id = last_event_ids[team_id]
    MatchTeamStats.objects.bulk_update(
        list(rows.values()),
        [
            "passes",
            "completed_passes",
            "shots",
            "shots_on_target",
            "goals",
            "xg",
            "possession_seconds",
            "possession",
            "pass_accuracy",
            "last_event",
        ],
    )


def _predecessor_key(event: Event) -> tuple:
    """Ordering key replicating the predecessor query's DESC ordering.

    (period, timestamp_ms, event_index, id) with NULL timestamps ranking
    below every real timestamp, exactly as MySQL sorts them.
    """
    timestamp_ms = (
        event.timestamp_ms if event.timestamp_ms is not None else float("-inf")
    )
    return (
        int(event.period or 0),
        timestamp_ms,
        int(event.event_index or 0),
        event.pk,
    )


def _allocate_possession_time(event: Event) -> None:
    previous_event = (
        Event.objects.filter(match=event.match)
        .exclude(pk=event.pk)
        .order_by("-period", "-timestamp_ms", "-event_index", "-id")
        .first()
    )
    transfer = _possession_transfer(event, previous_event)
    if transfer is None:
        return

    team_id, delta_seconds = transfer
    previous_stats, _ = MatchTeamStats.objects.get_or_create(
        match=previous_event.match,
        team_id=team_id,
    )
    MatchTeamStats.objects.filter(pk=previous_stats.pk).update(
        possession_seconds=F("possession_seconds") + delta_seconds
    )


def _refresh_derived_match_rates(match_id: int) -> None:
    stats_rows = list(
        MatchTeamStats.objects.select_for_update().filter(match_id=match_id)
    )
    total_possession_seconds = sum(row.possession_seconds for row in stats_rows)

    for row in stats_rows:
        possession = (
            round((row.possession_seconds / total_possession_seconds) * 100)
            if total_possession_seconds
            else 0
        )
        pass_accuracy = (
            round((row.completed_passes / row.passes) * 100, 2)
            if row.passes
            else 0.0
        )
        MatchTeamStats.objects.filter(pk=row.pk).update(
            possession=possession,
            pass_accuracy=pass_accuracy,
        )


def _event_seconds(event: Event) -> int:
    if event.timestamp_ms is not None:
        return int(event.timestamp_ms / 1000)
    return int(event.minute or 0) * 60 + int(event.second or 0)
