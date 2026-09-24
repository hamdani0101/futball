"""Derived analytics for human-collected events.

Human operators record WHAT/WHO/WHEN/WHERE/OUTCOME.
This module derives everything else (distance, angle, zone, xG,
pass length/direction, progressive/final-third/penalty-area flags).

Uses the existing pluggable xG interface in
:mod:`analytics.services.xg.calculator` — no hardcoded production model.
"""

from __future__ import annotations

import math

from analytics.services.xg.calculator import (
    ShotFeatures,
    calculate_shot_angle,
    calculate_shot_distance,
    calculate_xg,
)

# StatsBomb-style pitch (0-120 x 0-80). Single source of truth for coords.
PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0
FINAL_THIRD_X = 80.0
PENALTY_AREA_X = 102.5  # start of attacking penalty area (right end)
PENALTY_AREA_Y_TOP = 18.0
PENALTY_AREA_Y_BOTTOM = 62.0
PROGRESSIVE_THRESHOLD = 10.0


def shot_zone(x: float, y: float) -> str:
    """Return a coarse human-readable shot zone for a shot location."""
    x = float(x)
    y = float(y)
    if x >= PENALTY_AREA_X and PENALTY_AREA_Y_TOP <= y <= PENALTY_AREA_Y_BOTTOM:
        if x >= 114.0 and 30.0 <= y <= 50.0:
            return "six_yard"
        return "penalty_area"
    if x >= FINAL_THIRD_X:
        return "final_third_outside_box"
    if x >= 60.0:
        return "midfield_attacking"
    return "own_half_or_deep"


def derive_shot_metrics(
    x: float,
    y: float,
    *,
    body_part: str = "",
    shot_type: str = "",
    play_pattern: str = "",
    assist_type: str = "",
    under_pressure: bool = False,
) -> dict:
    """Calculate distance, angle, zone and xG for a shot location."""
    distance = round(calculate_shot_distance(x, y), 2)
    angle = round(calculate_shot_angle(x, y), 4)
    xg = calculate_xg(
        ShotFeatures(
            x=float(x),
            y=float(y),
            body_part=body_part or "",
            shot_type=shot_type or "",
            play_pattern=play_pattern or "",
            assist_type=assist_type or "",
            under_pressure=bool(under_pressure),
        )
    )
    return {
        "distance": distance,
        "angle": angle,
        "zone": shot_zone(x, y),
        "xg": xg,
        "is_big_chance": xg >= 0.3,
    }


def pass_length(x1: float, y1: float, x2: float, y2: float) -> float:
    return round(math.hypot(float(x2) - float(x1), float(y2) - float(y1)), 2)


def pass_angle(x1: float, y1: float, x2: float, y2: float) -> float:
    """Direction of the pass in radians (-pi..pi)."""
    return round(math.atan2(float(y2) - float(y1), float(x2) - float(x1)), 4)


def _distance_to_goal(x: float, y: float) -> float:
    return math.hypot(PITCH_LENGTH - float(x), (PITCH_WIDTH / 2) - float(y))


def is_progressive_pass(x1: float, y1: float, x2: float, y2: float) -> bool:
    return (_distance_to_goal(x1, y1) - _distance_to_goal(x2, y2)) >= PROGRESSIVE_THRESHOLD


def is_final_third_entry(x1: float, x2: float) -> bool:
    return float(x1) < FINAL_THIRD_X <= float(x2)


def is_penalty_area_entry(x2: float, y2: float) -> bool:
    return (
        float(x2) >= PENALTY_AREA_X
        and PENALTY_AREA_Y_TOP <= float(y2) <= PENALTY_AREA_Y_BOTTOM
    )


def derive_pass_metrics(x1: float, y1: float, x2: float, y2: float) -> dict:
    """Calculate length, direction and tactical flags for a pass."""
    return {
        "length": pass_length(x1, y1, x2, y2),
        "angle": pass_angle(x1, y1, x2, y2),
        "progressive": is_progressive_pass(x1, y1, x2, y2),
        "final_third_entry": is_final_third_entry(x1, x2),
        "penalty_area_entry": is_penalty_area_entry(x2, y2),
    }
