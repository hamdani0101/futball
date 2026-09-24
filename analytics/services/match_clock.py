"""Server-authoritative match clock and status transitions.

Display states are derived from the existing ``Match.status`` + ``period``
fields — no schema change:

- NOT_STARTED  = scheduled
- FIRST_HALF   = live, period 1
- HALF_TIME    = paused
- SECOND_HALF  = live, period 2+
- FULL_TIME    = finished

While the match is live the clock ticks server-side: the stored
``current_minute``/``current_second`` is the base and elapsed wall time since
``updated_at`` is added. The browser may animate the display but must never
be the canonical time; event endpoints fall back to this clock when the
client omits minute/second.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

NOT_STARTED = "NOT_STARTED"
FIRST_HALF = "FIRST_HALF"
HALF_TIME = "HALF_TIME"
SECOND_HALF = "SECOND_HALF"
FULL_TIME = "FULL_TIME"

START_MATCH = "start_match"
HALF_TIME_ACTION = "half_time"
START_SECOND_HALF = "start_second_half"
FULL_TIME_ACTION = "full_time"

VALID_ACTIONS = (START_MATCH, HALF_TIME_ACTION, START_SECOND_HALF, FULL_TIME_ACTION)

STATE_LABELS = {
    NOT_STARTED: "Not started",
    FIRST_HALF: "First half",
    HALF_TIME: "Half time",
    SECOND_HALF: "Second half",
    FULL_TIME: "Full time",
}


def display_state(match) -> str:
    """Return the operator-facing state for a match."""
    status = (match.status or "").lower()
    if status == "finished":
        return FULL_TIME
    if status == "paused":
        return HALF_TIME
    if status == "live":
        return SECOND_HALF if (match.period or 1) >= 2 else FIRST_HALF
    if status == "scheduled":
        return NOT_STARTED
    return status.upper() or NOT_STARTED


def is_running(match) -> bool:
    """True while the clock should tick (ball in play)."""
    return (match.status or "").lower() == "live"


def current_clock(match) -> tuple[int, int]:
    """Server-authoritative (minute, second), ticking while live."""
    base = int(match.current_minute or 0) * 60 + int(match.current_second or 0)
    if is_running(match) and match.updated_at:
        elapsed = (timezone.now() - match.updated_at).total_seconds()
        if elapsed > 0:
            base += int(elapsed)
    return divmod(max(base, 0), 60)


def clock_payload(match) -> dict:
    """Small clock/state payload for API responses and broadcasts."""
    minute, second = current_clock(match)
    state = display_state(match)
    return {
        "state": state,
        "label": STATE_LABELS.get(state, state),
        "minute": minute,
        "second": second,
        "period": match.period or 1,
        "running": is_running(match),
    }


def available_actions(match) -> list[str]:
    """State-appropriate controls; empty at full time."""
    state = display_state(match)
    if state == NOT_STARTED:
        return [START_MATCH]
    if state == FIRST_HALF:
        return [HALF_TIME_ACTION]
    if state == HALF_TIME:
        return [START_SECOND_HALF, FULL_TIME_ACTION]
    if state == SECOND_HALF:
        return [FULL_TIME_ACTION]
    return []


def transition(match, action: str):
    """Apply a validated clock transition; raises ValueError if illegal.

    Freeze transitions snapshot the ticking clock so the stored base stays
    authoritative after the clock stops.
    """
    if action not in VALID_ACTIONS:
        raise ValueError(f"Unknown clock action: {action}.")

    state = display_state(match)
    minute, second = current_clock(match)

    if action == START_MATCH:
        if state != NOT_STARTED:
            raise ValueError("Match can only be started from the not-started state.")
        match.status = "live"
        match.period = 1
        match.current_minute = 0
        match.current_second = 0
    elif action == HALF_TIME_ACTION:
        if state != FIRST_HALF:
            raise ValueError("Half time is only available during the first half.")
        match.status = "paused"
        match.current_minute = minute
        match.current_second = second
    elif action == START_SECOND_HALF:
        if state != HALF_TIME:
            raise ValueError("The second half can only start from half time.")
        match.status = "live"
        match.period = 2
        match.current_minute = 45
        match.current_second = 0
    elif action == FULL_TIME_ACTION:
        if state not in (SECOND_HALF, HALF_TIME):
            raise ValueError("Full time is only available after half time.")
        match.status = "finished"
        if state == SECOND_HALF:
            match.current_minute = minute
            match.current_second = second

    match.save(update_fields=["status", "period", "current_minute", "current_second", "updated_at"])
    return match


def collection_blocked_reason(match) -> str | None:
    """Why normal event collection is refused, or None if allowed."""
    if display_state(match) == FULL_TIME:
        return "Match is already full time."
    return None
