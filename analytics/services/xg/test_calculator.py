"""Tests for the xG calculator service."""

from unittest import TestCase

from analytics.services.xg.calculator import (
    PENALTY_XG,
    ShotFeatures,
    calculate_shot_angle,
    calculate_shot_distance,
    calculate_xg,
    features_from_statsbomb_event,
)


class XGCalculatorTests(TestCase):
    def test_penalty_has_fixed_xg(self):
        features = ShotFeatures(x=108, y=40, shot_type="Penalty")

        self.assertEqual(calculate_xg(features), PENALTY_XG)

    def test_close_central_shot_is_better_than_long_wide_header(self):
        close_central = ShotFeatures(x=114, y=40, body_part="Right Foot")
        long_wide_header = ShotFeatures(
            x=92,
            y=18,
            body_part="Head",
            under_pressure=True,
        )

        self.assertGreater(calculate_xg(close_central), calculate_xg(long_wide_header))

    def test_distance_and_angle_use_statsbomb_goal_location(self):
        self.assertEqual(calculate_shot_distance(120, 40), 0)
        self.assertGreater(calculate_shot_angle(118, 40), calculate_shot_angle(90, 10))

    def test_builds_features_from_statsbomb_event_payload(self):
        raw_event = {
            "location": [104.5, 38.0],
            "play_pattern": {"name": "From Corner"},
            "under_pressure": True,
            "shot": {
                "body_part": {"name": "Head"},
                "type": {"name": "Open Play"},
            },
        }

        features = features_from_statsbomb_event(raw_event)

        self.assertEqual(features.x, 104.5)
        self.assertEqual(features.y, 38.0)
        self.assertEqual(features.body_part, "Head")
        self.assertEqual(features.shot_type, "Open Play")
        self.assertEqual(features.play_pattern, "From Corner")
        self.assertTrue(features.under_pressure)
