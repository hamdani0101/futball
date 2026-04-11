"""Expected goals services."""

from .calculator import (
    ShotFeatures,
    calculate_match_xg,
    calculate_shot_angle,
    calculate_shot_distance,
    calculate_xg,
    calculate_xg_from_shot,
    features_from_statsbomb_event,
    recalculate_shots_xg,
    update_shot_metrics,
)

__all__ = [
    "ShotFeatures",
    "calculate_match_xg",
    "calculate_shot_angle",
    "calculate_shot_distance",
    "calculate_xg",
    "calculate_xg_from_shot",
    "features_from_statsbomb_event",
    "recalculate_shots_xg",
    "update_shot_metrics",
]
