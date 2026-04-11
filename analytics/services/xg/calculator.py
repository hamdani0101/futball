"""Expected-goals calculation from shot location and context."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from django.db.models import Sum


STATSBOMB_PITCH_LENGTH = 120.0
STATSBOMB_PITCH_WIDTH = 80.0
GOAL_CENTER_Y = STATSBOMB_PITCH_WIDTH / 2
GOAL_WIDTH = 8.0
PENALTY_XG = 0.76


@dataclass(frozen=True)
class ShotFeatures:
    """Inputs used by the lightweight xG model."""

    x: float
    y: float
    body_part: str = ""
    shot_type: str = ""
    play_pattern: str = ""
    under_pressure: bool = False


def calculate_shot_distance(x: float, y: float) -> float:
    """Return distance from the shot location to the centre of the goal."""
    return math.hypot(STATSBOMB_PITCH_LENGTH - float(x), GOAL_CENTER_Y - float(y))


def calculate_shot_angle(x: float, y: float) -> float:
    """Return the visible goal angle in radians from a StatsBomb shot location."""
    dx = max(STATSBOMB_PITCH_LENGTH - float(x), 0.1)
    dy = abs(GOAL_CENTER_Y - float(y))
    half_goal = GOAL_WIDTH / 2
    denominator = dx**2 + dy**2 - half_goal**2

    if denominator <= 0:
        return math.pi

    angle = math.atan((GOAL_WIDTH * dx) / denominator)
    return max(0.0, min(math.pi, angle))


def calculate_xg(features: ShotFeatures) -> float:
    """Estimate xG as a probability between 0 and 1."""
    if _normalize(features.shot_type) == "penalty":
        return PENALTY_XG

    distance = calculate_shot_distance(features.x, features.y)
    angle = calculate_shot_angle(features.x, features.y)

    logit = -1.35
    logit += -0.09 * distance
    logit += 1.25 * angle

    body_part = _normalize(features.body_part)
    if body_part == "head":
        logit -= 0.35
    elif body_part and body_part not in {"right_foot", "left_foot"}:
        logit -= 0.2

    shot_type = _normalize(features.shot_type)
    if shot_type == "free_kick":
        logit -= 0.55

    play_pattern = _normalize(features.play_pattern)
    if play_pattern == "corner":
        logit -= 0.25

    if features.under_pressure:
        logit -= 0.25

    probability = 1 / (1 + math.exp(-logit))
    return round(max(0.01, min(0.99, probability)), 4)


def calculate_xg_from_shot(shot) -> float:
    """Estimate xG for a Shot model instance without saving it."""
    return calculate_xg(
        ShotFeatures(
            x=shot.x,
            y=shot.y,
            body_part=shot.body_part,
            shot_type=shot.shot_type,
            play_pattern=shot.play_pattern,
            under_pressure=shot.under_pressure,
        )
    )


def update_shot_metrics(shot, *, save: bool = True):
    """Populate xG, distance, angle, and big-chance flags for a Shot instance."""
    shot.shot_distance = round(calculate_shot_distance(shot.x, shot.y), 2)
    shot.shot_angle = round(calculate_shot_angle(shot.x, shot.y), 4)
    shot.xg = calculate_xg_from_shot(shot)
    shot.is_big_chance = shot.xg >= 0.3

    if save:
        shot.save(
            update_fields=[
                "xg",
                "shot_distance",
                "shot_angle",
                "is_big_chance",
                "updated_at",
            ]
        )

    return shot


def recalculate_shots_xg(shots: Iterable, *, save: bool = True) -> int:
    """Recalculate xG metrics for each shot and return the number processed."""
    count = 0
    for shot in shots:
        update_shot_metrics(shot, save=save)
        count += 1
    return count


def calculate_match_xg(match):
    """Return per-team xG totals for a Match instance."""
    return {
        row["team_id"]: row["xg"] or 0.0
        for row in match.shots.values("team_id").annotate(xg=Sum("xg"))
    }


def features_from_statsbomb_event(raw_event) -> ShotFeatures:
    """Build ShotFeatures from a StatsBomb event payload."""
    location = raw_event.get("location") or [0, GOAL_CENTER_Y]
    shot = raw_event.get("shot") or {}

    return ShotFeatures(
        x=_safe_float(_list_get(location, 0), 0.0),
        y=_safe_float(_list_get(location, 1), GOAL_CENTER_Y),
        body_part=((shot.get("body_part") or {}).get("name") or ""),
        shot_type=((shot.get("type") or {}).get("name") or ""),
        play_pattern=((raw_event.get("play_pattern") or {}).get("name") or ""),
        under_pressure=bool(raw_event.get("under_pressure", False)),
    )


def _normalize(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _list_get(values, index):
    try:
        return values[index]
    except (IndexError, TypeError):
        return None


def _safe_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
