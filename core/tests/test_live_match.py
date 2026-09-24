"""Live Match realtime/operator tests: edit, broadcast, clock, status."""

from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import Event, MatchTeamStats
from core.models.save import Save
from core.models.shots import Shot
from core.tests.test_event_collection import make_match

Pass = __import__("core.models.pass", fromlist=["Pass"]).Pass


def _layer_calls(layer):
    return [c.args[1] for c in layer.group_send.call_args_list]


class LiveEditTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.match, self.home, self.away, self.squads = make_match()
        self.shooter = self.squads[self.home.id][0]
        kafka_patch = override_settings(KAFKA_ENABLED=False)
        kafka_patch.enable()
        self.addCleanup(kafka_patch.disable)

    def _create(self, payload):
        return self.client.post(
            f"/api/match/{self.match.pk}/events/", payload, format="json"
        )

    def _shot(self, x=105.0, outcome="off_target"):
        resp = self._create({
            "type": "shot", "period": 1, "minute": 67, "second": 24,
            "team": self.home.id, "player": self.shooter.id,
            "x": x, "y": 40.0,
            "payload": {"outcome": outcome, "body_part": "right_foot"},
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        return Event.objects.get(match=self.match, type__in=("shot", "goal"))

    def test_patch_shot_location_updates_xg(self):
        event = self._shot(x=105.0)
        old_xg = event.shot_detail.xg
        resp = self.client.patch(
            f"/api/match/{self.match.pk}/events/{event.pk}/",
            {"x": 112.0, "y": 40.0}, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        event.shot_detail.refresh_from_db()
        # Closer to goal → higher xG; all derived fields recalculated.
        self.assertGreater(event.shot_detail.xg, old_xg)
        self.assertGreater(event.shot_detail.shot_distance, 0)
        self.assertGreater(event.shot_detail.shot_angle, 0)

    def test_patch_pass_updates_derived_flags(self):
        passer = self.squads[self.home.id][1]
        resp = self._create({
            "type": "pass", "period": 1, "minute": 10, "second": 5,
            "team": self.home.id, "player": passer.id,
            "x": 40.0, "y": 40.0,
            "payload": {"end_x": 50.0, "end_y": 40.0, "outcome": "complete"},
        })
        self.assertEqual(resp.status_code, 201)
        event = Event.objects.get(match=self.match)
        resp = self.client.patch(
            f"/api/match/{self.match.pk}/events/{event.pk}/",
            {"payload": {"end_x": 85.0, "end_y": 40.0}}, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        event.pass_detail.refresh_from_db()
        self.assertAlmostEqual(event.pass_detail.length, 45.0, places=1)

    def test_patch_goal_updates_score(self):
        event = self._shot(outcome="off_target")
        home_stats = MatchTeamStats.objects.get(match=self.match, team=self.home)
        self.assertEqual(home_stats.goals, 0)
        resp = self.client.patch(
            f"/api/match/{self.match.pk}/events/{event.pk}/",
            {"payload": {"outcome": "goal"}}, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        home_stats.refresh_from_db()
        self.assertEqual(home_stats.goals, 1)

    def test_delete_goal_updates_score(self):
        resp = self._create({
            "type": "goal", "period": 2, "minute": 80, "second": 0,
            "team": self.home.id, "player": self.shooter.id,
            "x": 112.0, "y": 38.0, "payload": {"body_part": "right_foot"},
        })
        self.assertEqual(resp.status_code, 201)
        event = Event.objects.get(match=self.match)
        self.assertEqual(
            MatchTeamStats.objects.get(match=self.match, team=self.home).goals, 1
        )
        resp = self.client.delete(f"/api/match/{self.match.pk}/events/{event.pk}/")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(
            MatchTeamStats.objects.get(match=self.match, team=self.home).goals, 0
        )

    def test_patch_rejects_wrong_team_player(self):
        event = self._shot()
        outsider = self.squads[self.away.id][0]
        resp = self.client.patch(
            f"/api/match/{self.match.pk}/events/{event.pk}/",
            {"player": outsider.id}, format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_server_clock_stamps_unspecified_time(self):
        resp = self._create({
            "type": "duel", "team": self.home.id, "player": self.shooter.id,
            "x": 60.0, "y": 40.0, "payload": {},
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        event = Event.objects.get(match=self.match)
        self.assertIsNotNone(event.minute)


class BroadcastTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.match, self.home, self.away, self.squads = make_match()
        self.shooter = self.squads[self.home.id][0]
        kafka_patch = override_settings(KAFKA_ENABLED=False)
        kafka_patch.enable()
        self.addCleanup(kafka_patch.disable)
        layer_patch = mock.patch("core.consumers.get_channel_layer")
        self.layer = mock.MagicMock()
        from unittest.mock import AsyncMock
        self.layer.group_send = AsyncMock()
        layer_patch.start()
        layer_patch.return_value = self.layer
        self.addCleanup(layer_patch.stop)
        # Patch the already-imported reference inside core.consumers.
        import core.consumers as consumers
        self._orig = consumers.get_channel_layer
        consumers.get_channel_layer = lambda: self.layer
        self.addCleanup(setattr, consumers, "get_channel_layer", self._orig)

    def _shot_payload(self):
        return {
            "type": "shot", "period": 1, "minute": 20, "second": 0,
            "team": self.home.id, "player": self.shooter.id,
            "x": 105.0, "y": 40.0,
            "payload": {"outcome": "off_target"},
        }

    def test_create_broadcasts(self):
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(
                f"/api/match/{self.match.pk}/events/", self._shot_payload(), format="json"
            )
        self.assertEqual(resp.status_code, 201)
        changes = _layer_calls(self.layer)
        self.assertTrue(changes)
        self.assertEqual(changes[-1]["data"]["change"], "created")
        self.assertIsNotNone(changes[-1]["data"]["event"])

    def test_edit_broadcasts(self):
        resp = self.client.post(
            f"/api/match/{self.match.pk}/events/", self._shot_payload(), format="json"
        )
        event_id = resp.json()["id"]
        self.layer.group_send.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.patch(
                f"/api/match/{self.match.pk}/events/{event_id}/",
                {"payload": {"outcome": "blocked"}}, format="json",
            )
        self.assertEqual(resp.status_code, 200)
        changes = _layer_calls(self.layer)
        self.assertTrue(changes)
        self.assertEqual(changes[-1]["data"]["change"], "edited")

    def test_delete_broadcasts(self):
        resp = self.client.post(
            f"/api/match/{self.match.pk}/events/", self._shot_payload(), format="json"
        )
        event_id = resp.json()["id"]
        self.layer.group_send.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.delete(
                f"/api/match/{self.match.pk}/events/{event_id}/"
            )
        self.assertEqual(resp.status_code, 204)
        changes = _layer_calls(self.layer)
        self.assertTrue(changes)
        self.assertEqual(changes[-1]["data"]["change"], "deleted")
        self.assertEqual(changes[-1]["data"]["event"]["id"], event_id)

    def test_websocket_failure_does_not_fail_creation(self):
        self.layer.group_send.side_effect = Exception("ws down")
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(
                f"/api/match/{self.match.pk}/events/", self._shot_payload(), format="json"
            )
        # DB is the source of truth: event persists despite WS failure.
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(Event.objects.filter(match=self.match).count(), 1)

    def test_two_clients_receive_same_state(self):
        client2 = APIClient()
        resp = self.client.post(
            f"/api/match/{self.match.pk}/events/", self._shot_payload(), format="json"
        )
        self.assertEqual(resp.status_code, 201)
        snapshot = client2.get(f"/api/live-match/{self.match.pk}").json()
        self.assertEqual(snapshot["score"], {"home": 0, "away": 0})
        self.assertEqual(len(snapshot["recent_events"]), 1)
        self.assertEqual(snapshot["recent_events"][0]["id"], resp.json()["id"])


class ClockTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.match, self.home, self.away, self.squads = make_match()
        kafka_patch = override_settings(KAFKA_ENABLED=False)
        kafka_patch.enable()
        self.addCleanup(kafka_patch.disable)

    def _clock(self, action=None):
        if action is None:
            return self.client.get(f"/api/match/{self.match.pk}/clock/")
        return self.client.post(
            f"/api/match/{self.match.pk}/clock/", {"action": action}, format="json"
        )

    def test_full_transition_sequence(self):
        self.assertEqual(self._clock().json()["state"], "NOT_STARTED")
        data = self._clock("start_match").json()
        self.assertEqual(data["state"], "FIRST_HALF")
        self.assertEqual((data["minute"], data["second"]), (0, 0))
        data = self._clock("half_time").json()
        self.assertEqual(data["state"], "HALF_TIME")
        self.assertFalse(data["running"])
        data = self._clock("start_second_half").json()
        self.assertEqual(data["state"], "SECOND_HALF")
        self.assertEqual((data["minute"], data["second"]), (45, 0))
        data = self._clock("full_time").json()
        self.assertEqual(data["state"], "FULL_TIME")
        self.assertEqual(data["available_actions"], [])

    def test_invalid_transitions_rejected(self):
        # Cannot skip straight to the second half.
        resp = self._clock("start_second_half")
        self.assertEqual(resp.status_code, 400)
        # Cannot end a match that never started.
        self.assertEqual(self._clock("full_time").status_code, 400)
        # Unknown actions rejected.
        self.assertEqual(self._clock("tea_break").status_code, 400)
        # Half time only from the first half.
        self._clock("start_match")
        self._clock("half_time")
        self.assertEqual(self._clock("half_time").status_code, 400)

    def test_full_time_blocks_creation_but_allows_correction(self):
        shooter = self.squads[self.home.id][0]
        payload = {
            "type": "shot", "period": 1, "minute": 10, "second": 0,
            "team": self.home.id, "player": shooter.id,
            "x": 105.0, "y": 40.0, "payload": {"outcome": "off_target"},
        }
        self.assertEqual(self.client.post(
            f"/api/match/{self.match.pk}/events/", payload, format="json").status_code, 201)
        event_id = Event.objects.get(match=self.match).pk
        for action in ("start_match", "half_time", "start_second_half", "full_time"):
            self.assertEqual(self._clock(action).status_code, 200)
        resp = self.client.post(
            f"/api/match/{self.match.pk}/events/", payload, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("full time", resp.json()["detail"].lower())
        # Historical correction via PATCH stays available.
        resp = self.client.patch(
            f"/api/match/{self.match.pk}/events/{event_id}/",
            {"payload": {"outcome": "blocked"}}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_reconnect_refresh_carries_clock_and_state(self):
        self._clock("start_match")
        snapshot = self.client.get(f"/api/live-match/{self.match.pk}").json()
        self.assertIn("clock", snapshot)
        self.assertEqual(snapshot["clock"]["state"], "FIRST_HALF")
        self.assertTrue(snapshot["clock"]["running"])
        self.assertIn("match_state", snapshot)
        self.assertIn("half_time", snapshot["match_state"]["available_actions"])


class ConsistencyTest(TestCase):
    """No orphans, no duplicates, payloads fit for timeline + edit."""

    def setUp(self):
        self.client = APIClient()
        self.match, self.home, self.away, self.squads = make_match()
        self.shooter = self.squads[self.home.id][0]
        kafka_patch = override_settings(KAFKA_ENABLED=False)
        kafka_patch.enable()
        self.addCleanup(kafka_patch.disable)

    def test_goal_payload_includes_outcome_and_xg(self):
        resp = self.client.post(
            f"/api/match/{self.match.pk}/events/",
            {"type": "goal", "period": 2, "minute": 80, "second": 0,
             "team": self.home.id, "player": self.shooter.id,
             "x": 112.0, "y": 38.0, "payload": {"body_part": "right_foot"}},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["payload"]["outcome"], "goal")
        self.assertGreater(data["payload"]["xg"], 0)

    def test_pass_payload_includes_recipient_name(self):
        passer = self.squads[self.home.id][1]
        recipient = self.squads[self.home.id][2]
        resp = self.client.post(
            f"/api/match/{self.match.pk}/events/",
            {"type": "pass", "period": 1, "minute": 10, "second": 0,
             "team": self.home.id, "player": passer.id,
             "x": 40.0, "y": 40.0,
             "payload": {"end_x": 60.0, "end_y": 40.0, "outcome": "complete",
                         "recipient_id": recipient.id}},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["payload"]["recipient_name"], recipient.name)

    def test_duplicate_post_with_same_key_returns_single_row(self):
        payload = {
            "type": "shot", "period": 1, "minute": 20, "second": 0,
            "team": self.home.id, "player": self.shooter.id,
            "x": 105.0, "y": 40.0,
            "payload": {"outcome": "off_target", "external_event_id": "op-retry-1"},
        }
        first = self.client.post(
            f"/api/match/{self.match.pk}/events/", payload, format="json")
        second = self.client.post(
            f"/api/match/{self.match.pk}/events/", payload, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(Event.objects.filter(match=self.match).count(), 1)

    def test_delete_saved_shot_removes_detail_and_linked_save(self):
        keeper = self.squads[self.away.id][0]
        resp = self.client.post(
            f"/api/match/{self.match.pk}/events/",
            {"type": "shot", "period": 1, "minute": 67, "second": 24,
             "team": self.home.id, "player": self.shooter.id,
             "x": 110.0, "y": 40.0,
             "payload": {"outcome": "saved", "save_player_id": keeper.id}},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        shot_event = Event.objects.get(match=self.match, type="shot")
        shot_pk = shot_event.shot_detail.pk
        self.assertEqual(Event.objects.filter(match=self.match).count(), 2)
        resp = self.client.delete(
            f"/api/match/{self.match.pk}/events/{shot_event.pk}/")
        self.assertEqual(resp.status_code, 204)
        # No orphan detail rows, no orphan linked save event.
        self.assertFalse(Shot.objects.filter(pk=shot_pk).exists())
        self.assertFalse(Save.objects.filter(originating_shot_id=shot_pk).exists())
        self.assertEqual(Event.objects.filter(match=self.match).count(), 0)

    def test_delete_pass_removes_detail_row(self):
        passer = self.squads[self.home.id][1]
        resp = self.client.post(
            f"/api/match/{self.match.pk}/events/",
            {"type": "pass", "period": 1, "minute": 10, "second": 0,
             "team": self.home.id, "player": passer.id,
             "x": 40.0, "y": 40.0,
             "payload": {"end_x": 60.0, "end_y": 40.0, "outcome": "complete"}},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        event_id = resp.json()["id"]
        pass_pk = Event.objects.get(pk=event_id).pass_detail.pk
        self.client.delete(f"/api/match/{self.match.pk}/events/{event_id}/")
        self.assertFalse(Pass.objects.filter(pk=pass_pk).exists())
