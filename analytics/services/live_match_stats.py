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


@transaction.atomic
def update_live_match_stats(event: Event) -> LiveMatchStatsSnapshot:
    """Incrementally update match stats for a newly persisted event."""
    _allocate_possession_time(event)

    stats, _ = MatchTeamStats.objects.select_for_update().get_or_create(
        match=event.match,
        team=event.team,
    )

    update_fields = {"last_event": event}

    if event.type == Event.Type.PASS:
        pass_detail = getattr(event, "pass_detail", None)
        if pass_detail:
            update_fields["passes"] = F("passes") + 1
            if pass_detail.outcome == Pass.Outcome.COMPLETE:
                update_fields["completed_passes"] = F("completed_passes") + 1

    elif event.type == Event.Type.SHOT:
        shot_detail = getattr(event, "shot_detail", None)
        if shot_detail:
            update_fields["shots"] = F("shots") + 1
            update_fields["xg"] = F("xg") + float(shot_detail.xg or 0)
            if shot_detail.outcome in ON_TARGET_SHOT_OUTCOMES:
                update_fields["shots_on_target"] = F("shots_on_target") + 1
            if shot_detail.outcome == Shot.Outcome.GOAL:
                update_fields["score"] = F("score") + 1

    elif event.type == GOAL_EVENT_TYPE:
        update_fields["score"] = F("score") + 1

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


def _allocate_possession_time(event: Event) -> None:
    previous_event = (
        Event.objects.filter(match=event.match)
        .exclude(pk=event.pk)
        .order_by("-period", "-timestamp_ms", "-event_index", "-id")
        .first()
    )
    if not previous_event or not previous_event.team_id:
        return

    delta_seconds = _event_seconds(event) - _event_seconds(previous_event)
    if delta_seconds <= 0 or delta_seconds > 180:
        return

    previous_stats, _ = MatchTeamStats.objects.get_or_create(
        match=previous_event.match,
        team=previous_event.team,
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
