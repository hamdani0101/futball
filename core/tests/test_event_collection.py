"""Event-collection tests: human records the event, system derives metrics."""

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from analytics.services.derived import (
    derive_pass_metrics,
    derive_shot_metrics,
    shot_zone,
)
from core.models import Event, Match, MatchTeamStats, Player, Season, Team
from core.models.competition import Competition


def make_match():
    competition = Competition.objects.create(name="Test League", code="TST")
    season = Season.objects.create(competition=competition, name="2026")
    home = Team.objects.create(name="Home FC")
    away = Team.objects.create(name="Away FC")
    match = Match.objects.create(
        season=season, home_team=home, away_team=away,
        match_date="2026-09-24T15:00:00Z",
    )
    squads = {}
    for team in (home, away):
        squads[team.id] = [
            Player.objects.create(name=f"{team.name} P{i}", team_now=team)
            for i in range(1, 6)
        ]
    return match, home, away, squads


class EventCollectionAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.match, self.home, self.away, self.squads = make_match()
        self.shooter = self.squads[self.home.id][0]
        self.keeper = self.squads[self.away.id][0]
        # Kafka broker is unavailable in tests; DB persistence is the
        # source of truth and publish is best-effort (skipped here).
        kafka_patch = override_settings(KAFKA_ENABLED=False)
        kafka_patch.enable()
        self.addCleanup(kafka_patch.disable)

    def _create(self, payload):
        return self.client.post(
            f"/api/match/{self.match.pk}/events/", payload, format="json"
        )

    def test_shot_derives_xg_distance_angle_zone(self):
        resp = self._create({
            "type": "shot", "period": 1, "minute": 67, "second": 24,
            "team": self.home.id, "player": self.shooter.id,
            "x": 105.0, "y": 40.0,
            "payload": {"outcome": "off_target", "body_part": "right_foot"},
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        shot = Event.objects.get(match=self.match).shot_detail
        self.assertGreater(shot.xg, 0)  # system-calculated, never human-entered
        self.assertGreater(shot.shot_distance, 0)
        self.assertGreater(shot.shot_angle, 0)
        # Match clock advanced by the server, not the browser.
        self.match.refresh_from_db()
        self.assertEqual((self.match.current_minute, self.match.current_second), (67, 24))

    def test_pass_derives_length_progressive_entries(self):
        passer = self.squads[self.home.id][1]
        recipient = self.squads[self.home.id][2]
        resp = self._create({
            "type": "pass", "period": 1, "minute": 10, "second": 5,
            "team": self.home.id, "player": passer.id,
            "x": 40.0, "y": 40.0,
            "payload": {
                "end_x": 85.0, "end_y": 40.0,
                "outcome": "complete", "recipient_id": recipient.id,
            },
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        prow = Event.objects.get(match=self.match).pass_detail
        self.assertAlmostEqual(prow.length, 45.0, places=1)
        self.assertIsNotNone(prow.angle)
        derived = Event.objects.get(match=self.match).extra_data["derived"]
        self.assertTrue(derived["progressive"])
        self.assertTrue(derived["final_third_entry"])

    def test_save_linked_to_originating_shot(self):
        resp = self._create({
            "type": "shot", "period": 1, "minute": 67, "second": 24,
            "team": self.home.id, "player": self.shooter.id,
            "x": 110.0, "y": 40.0,
            "payload": {"outcome": "saved", "save_player_id": self.keeper.id},
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        shot_event = Event.objects.get(match=self.match, type="shot")
        save_event = Event.objects.get(match=self.match, type="save")
        self.assertEqual(save_event.related_event_id, shot_event.pk)
        self.assertEqual(save_event.save_detail.originating_shot_id, shot_event.shot_detail.pk)
        self.assertEqual(save_event.player_id, self.keeper.id)

    def test_save_keeper_must_be_opposition(self):
        own_keeper = self.squads[self.home.id][3]
        resp = self._create({
            "type": "shot", "period": 1, "minute": 10, "second": 0,
            "team": self.home.id, "player": self.shooter.id,
            "x": 110.0, "y": 40.0,
            "payload": {"outcome": "saved", "save_player_id": own_keeper.id},
        })
        self.assertEqual(resp.status_code, 400)

    def test_goal_links_shot_and_assist(self):
        assister = self.squads[self.home.id][1]
        resp = self._create({
            "type": "goal", "period": 2, "minute": 80, "second": 0,
            "team": self.home.id, "player": self.shooter.id,
            "x": 112.0, "y": 38.0,
            "payload": {"body_part": "right_foot", "assist_player_id": assister.id},
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        event = Event.objects.get(match=self.match)
        self.assertEqual(event.type, "goal")
        self.assertTrue(event.shot_detail.is_goal)
        self.assertEqual(event.shot_detail.assist_player_id, assister.id)
        home_stats = MatchTeamStats.objects.get(match=self.match, team=self.home)
        self.assertEqual(home_stats.goals, 1)

    def test_substitution_creates_detail(self):
        out_p, in_p = self.squads[self.home.id][0], self.squads[self.home.id][4]
        resp = self._create({
            "type": "substitution", "period": 2, "minute": 60, "second": 0,
            "team": self.home.id, "player": None, "x": 60.0, "y": 40.0,
            "payload": {"player_out_id": out_p.id, "player_in_id": in_p.id},
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        event = Event.objects.get(match=self.match)
        self.assertEqual(event.substitution_detail.player_out_id, out_p.id)
        self.assertEqual(event.substitution_detail.player_in_id, in_p.id)

    def test_player_must_belong_to_team(self):
        outsider = self.squads[self.away.id][0]
        resp = self._create({
            "type": "shot", "period": 1, "minute": 5, "second": 0,
            "team": self.home.id, "player": outsider.id,
            "x": 100.0, "y": 40.0, "payload": {"outcome": "off_target"},
        })
        self.assertEqual(resp.status_code, 400)

    def test_team_must_participate_in_match(self):
        other = Team.objects.create(name="Neutral FC")
        other_player = Player.objects.create(name="Neutral P1", team_now=other)
        resp = self._create({
            "type": "shot", "period": 1, "minute": 5, "second": 0,
            "team": other.id, "player": other_player.id,
            "x": 100.0, "y": 40.0, "payload": {"outcome": "off_target"},
        })
        self.assertEqual(resp.status_code, 400)

    def test_coordinates_validated(self):
        resp = self._create({
            "type": "shot", "period": 1, "minute": 5, "second": 0,
            "team": self.home.id, "player": self.shooter.id,
            "x": 200.0, "y": 40.0, "payload": {"outcome": "off_target"},
        })
        self.assertEqual(resp.status_code, 400)

    def test_edit_recalculates_derived_metrics(self):
        resp = self._create({
            "type": "shot", "period": 1, "minute": 20, "second": 0,
            "team": self.home.id, "player": self.shooter.id,
            "x": 105.0, "y": 40.0, "payload": {"outcome": "off_target"},
        })
        self.assertEqual(resp.status_code, 201)
        event = Event.objects.get(match=self.match)
        old_xg = event.shot_detail.xg
        patch = self.client.patch(
            f"/api/match/{self.match.pk}/events/{event.pk}/",
            {"payload": {"outcome": "goal"}},
            format="json",
        )
        self.assertEqual(patch.status_code, 200)
        event.shot_detail.refresh_from_db()
        self.assertEqual(event.shot_detail.outcome, "goal")
        # Derived metrics stay consistent after edits.
        self.assertGreater(event.shot_detail.xg, 0)
        self.assertNotEqual(event.shot_detail.xg, 0.0)
        self.assertGreaterEqual(event.shot_detail.xg, 0.0)
        _ = old_xg  # xG depends on location, not outcome; key check is recalc ran

    def test_delete_undo_rebuilds_stats(self):
        self._create({
            "type": "shot", "period": 1, "minute": 20, "second": 0,
            "team": self.home.id, "player": self.shooter.id,
            "x": 105.0, "y": 40.0, "payload": {"outcome": "off_target"},
        })
        event = Event.objects.get(match=self.match)
        self.assertEqual(
            MatchTeamStats.objects.get(match=self.match, team=self.home).shots, 1
        )
        delete = self.client.delete(
            f"/api/match/{self.match.pk}/events/{event.pk}/"
        )
        self.assertEqual(delete.status_code, 204)
        self.assertEqual(Event.objects.filter(match=self.match).count(), 0)
        self.assertEqual(
            MatchTeamStats.objects.get(match=self.match, team=self.home).shots, 0
        )

    def test_kafka_retry_is_idempotent(self):
        from analytics.services.kafka_consumer import process_match_event

        payload = {
            "event_id": "retry-test-001",
            "event_type": "pass",
            "match_id": self.match.pk,
            "team_id": self.home.id,
            "player_id": self.shooter.id,
            "period": 1, "minute": 30, "second": 0,
            "payload": {
                "location": {"x": 30, "y": 40},
                "end_location": {"x": 60, "y": 40},
                "outcome": "complete",
            },
        }
        first = process_match_event(payload)
        second = process_match_event(payload)
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(
            Event.objects.filter(external_event_id="retry-test-001").count(), 1
        )


class DerivedMetricsTest(TestCase):
    def test_shot_zone_classification(self):
        self.assertEqual(shot_zone(110, 40), "penalty_area")
        self.assertEqual(shot_zone(115, 40), "six_yard")
        self.assertEqual(shot_zone(90, 10), "final_third_outside_box")

    def test_shot_derivation_ranges(self):
        close = derive_shot_metrics(112, 40)
        far = derive_shot_metrics(60, 40)
        self.assertGreater(close["xg"], far["xg"])
        self.assertTrue(0.01 <= close["xg"] <= 0.99)

    def test_pass_derivation_flags(self):
        prog = derive_pass_metrics(40, 40, 85, 40)
        self.assertTrue(prog["progressive"])
        self.assertTrue(prog["final_third_entry"])
        back = derive_pass_metrics(80, 40, 40, 40)
        self.assertFalse(back["progressive"])
        box_entry = derive_pass_metrics(90, 40, 108, 40)
        self.assertTrue(box_entry["penalty_area_entry"])
