"""Analytics-pipeline validation against a deterministic event stream.

Every expectation below is hand-derived in
``core.tests.analytics_fixture``. Statistics are never inserted manually;
all totals come from replaying the fixture through the real production path
(API validation -> derived metrics -> database -> aggregate update).
"""

from collections import Counter

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from analytics.services.derived import (
    is_final_third_entry,
    is_penalty_area_entry,
    is_progressive_pass,
    pass_angle,
)
from analytics.services.passing import (
    get_player_passing_stats,
    get_team_passing_stats,
)
from analytics.services.player_metrics import get_player_profile_stats
from analytics.services.xg.calculator import ShotFeatures, calculate_xg
from core.models import Event, MatchTeamStats
from core.models.save import Save
from core.models.shots import Shot
from core.tests import analytics_fixture as fx

Pass = __import__("core.models.pass", fromlist=["Pass"]).Pass


def replay_stream(client, match, events):
    """POST a full event stream through the real API. Returns key -> body."""
    bodies = {}
    for spec in events:
        body = {k: v for k, v in spec.items() if k != "key"}
        resp = client.post(f"/api/match/{match.pk}/events/", body, format="json")
        assert resp.status_code == 201, f"{spec['key']}: {resp.content!r}"
        bodies[spec["key"]] = resp.json()
    return bodies


def fresh_client(testcase):
    testcase.client = APIClient()
    patcher = override_settings(KAFKA_ENABLED=False)
    patcher.enable()
    testcase.addCleanup(patcher.disable)


class FixtureReplayTest(TestCase):
    """Sections 2, 4, 7: stream shape, match totals, team totals."""

    def setUp(self):
        fresh_client(self)
        self.match, self.home, self.away, self.players = fx.make_fixture_match()
        self.events = fx.fixture_events(self.match, self.home, self.away, self.players)
        replay_stream(self.client, self.match, self.events)

    def _row(self, team):
        return MatchTeamStats.objects.get(match=self.match, team=team)

    def test_event_stream_shape(self):
        self.assertEqual(Event.objects.filter(match=self.match).count(),
                         fx.EXPECTED_EVENT_COUNT)
        self.assertEqual(Shot.objects.filter(match=self.match).count(), 5)
        self.assertEqual(Pass.objects.filter(match=self.match).count(), 6)
        self.assertEqual(Save.objects.filter(match=self.match).count(),
                         fx.EXPECTED_SAVE_COUNT)
        types = Counter(Event.objects.filter(match=self.match)
                        .values_list("type", flat=True))
        self.assertEqual(types, {
            "pass": 6, "shot": 4, "goal": 1, "save": 1,
            "foul": 1, "card": 1, "substitution": 1,
        })

    def test_match_totals_home(self):
        row = self._row(self.home)
        exp = fx.EXPECTED_MATCH_TOTALS["home"]
        self.assertEqual(row.goals, exp["goals"])
        self.assertEqual(row.shots, exp["shots"])
        self.assertEqual(row.shots_on_target, exp["shots_on_target"])
        self.assertEqual(row.passes, exp["passes"])
        self.assertEqual(row.completed_passes, exp["completed_passes"])
        passing = get_team_passing_stats(self.home, match=self.match)
        self.assertEqual(passing["progressive_passes"], exp["progressive_passes"])
        self.assertEqual(passing["passes"], exp["passes"])
        self.assertEqual(passing["completed_passes"], exp["completed_passes"])

    def test_match_totals_away(self):
        row = self._row(self.away)
        exp = fx.EXPECTED_MATCH_TOTALS["away"]
        self.assertEqual(row.goals, exp["goals"])
        self.assertEqual(row.shots, exp["shots"])
        self.assertEqual(row.shots_on_target, exp["shots_on_target"])
        self.assertEqual(row.passes, exp["passes"])
        self.assertEqual(row.completed_passes, exp["completed_passes"])
        passing = get_team_passing_stats(self.away, match=self.match)
        self.assertEqual(passing["progressive_passes"], exp["progressive_passes"])

    def test_shot_outcome_splits(self):
        for side, team in (("home", self.home), ("away", self.away)):
            counts = Counter(Shot.objects.filter(match=self.match, team=team)
                             .values_list("outcome", flat=True))
            exp = fx.EXPECTED_MATCH_TOTALS[side]
            self.assertEqual(counts.get("goal", 0), exp["goals"])
            self.assertEqual(counts.get("saved", 0), exp["saved"])
            self.assertEqual(counts.get("blocked", 0), exp["blocked"])
            self.assertEqual(counts.get("off_target", 0), exp["off_target"])
            self.assertEqual(counts.get("wayward", 0), exp["wayward"])

    def test_pass_derived_flags_match_hand_derivation(self):
        for spec in self.events:
            if spec["type"] != "pass":
                continue
            key = spec["key"]
            prow = Pass.objects.get(event__external_event_id=key)
            exp_prog, exp_ft, exp_pa, exp_len = fx.EXPECTED_PASS_FLAGS[key]
            derived = prow.event.extra_data["derived"]
            self.assertEqual(derived["progressive"], exp_prog, key)
            self.assertEqual(derived["final_third_entry"], exp_ft, key)
            self.assertEqual(derived["penalty_area_entry"], exp_pa, key)
            self.assertAlmostEqual(prow.length, exp_len, places=1, msg=key)
            # Stored coordinates reproduce the same flags through the
            # production helpers (no hidden inputs).
            self.assertEqual(
                is_progressive_pass(prow.x, prow.y, prow.end_x, prow.end_y),
                exp_prog, key)
            self.assertEqual(is_final_third_entry(prow.x, prow.end_x), exp_ft, key)
            self.assertEqual(
                is_penalty_area_entry(prow.end_x, prow.end_y), exp_pa, key)
            self.assertAlmostEqual(prow.angle,
                                   pass_angle(prow.x, prow.y, prow.end_x, prow.end_y),
                                   places=3, msg=key)

    def test_entry_counts_per_team(self):
        got = {"home": {"ft": 0, "pa": 0}, "away": {"ft": 0, "pa": 0}}
        for prow in Pass.objects.filter(match=self.match).select_related("team"):
            side = "home" if prow.team_id == self.home.id else "away"
            derived = prow.event.extra_data["derived"]
            got[side]["ft"] += int(derived["final_third_entry"])
            got[side]["pa"] += int(derived["penalty_area_entry"])
        self.assertEqual(got["home"]["ft"],
                         fx.EXPECTED_MATCH_TOTALS["home"]["final_third_entries"])
        self.assertEqual(got["home"]["pa"],
                         fx.EXPECTED_MATCH_TOTALS["home"]["penalty_area_entries"])
        self.assertEqual(got["away"]["ft"],
                         fx.EXPECTED_MATCH_TOTALS["away"]["final_third_entries"])
        self.assertEqual(got["away"]["pa"],
                         fx.EXPECTED_MATCH_TOTALS["away"]["penalty_area_entries"])

    def test_save_goal_foul_card_sub_linkage(self):
        keeper = self.players["A1"]
        self.assertEqual(Save.objects.filter(match=self.match,
                                             player=keeper).count(), 1)
        save = Save.objects.get(match=self.match, player=keeper)
        shot = Shot.objects.get(match=self.match, outcome="saved")
        self.assertEqual(save.originating_shot_id, shot.pk)
        self.assertEqual(save.event.related_event_id, shot.event_id)
        goal = Shot.objects.get(match=self.match, is_goal=True)
        self.assertEqual(goal.assist_player, self.players["H10"])
        self.assertEqual(
            Event.objects.filter(match=self.match, type="foul").count(), 1)
        self.assertEqual(
            Event.objects.filter(match=self.match, type="card").count(), 1)
        sub = Event.objects.get(match=self.match,
                                type="substitution").substitution_detail
        self.assertEqual(sub.player_out, self.players["H7"])
        self.assertEqual(sub.player_in, self.players["H2"])

    def test_goal_counted_once_with_shot_and_xg(self):
        """A goal contributes shots/on-target/xG/goals exactly once."""
        row = self._row(self.home)
        goal_shot = Shot.objects.get(match=self.match, is_goal=True)
        self.assertEqual(Shot.objects.filter(match=self.match,
                                             team=self.home).count(), row.shots)
        home_xg = sum(s.xg for s in Shot.objects.filter(match=self.match,
                                                        team=self.home))
        self.assertAlmostEqual(row.xg, home_xg, places=3)
        # The goal's xG is inside the team total exactly once.
        non_goal_xg = sum(s.xg for s in Shot.objects.filter(
            match=self.match, team=self.home, is_goal=False))
        self.assertAlmostEqual(row.xg - non_goal_xg, goal_shot.xg, places=3)
        self.assertGreater(goal_shot.xg, 0)


class PlayerTotalsTest(TestCase):
    """Section 3: every player total derived from events only."""

    def setUp(self):
        fresh_client(self)
        self.match, self.home, self.away, self.players = fx.make_fixture_match()
        replay_stream(self.client, self.match,
                      fx.fixture_events(self.match, self.home, self.away, self.players))

    def test_player_totals(self):
        for code, exp in fx.EXPECTED_PLAYER_TOTALS.items():
            player = self.players[code]
            profile = get_player_profile_stats(player)
            passing = get_player_passing_stats(player, match=self.match)
            with self.subTest(player=code):
                self.assertEqual(profile["shots"], exp["shots"])
                self.assertEqual(profile["goals"], exp["goals"])
                self.assertEqual(passing["passes"], exp["passes"])
                self.assertEqual(passing["completed_passes"], exp["completed"])
                self.assertEqual(Save.objects.filter(match=self.match,
                                                     player=player).count(),
                                 exp["saves"])
                self.assertEqual(Event.objects.filter(
                    match=self.match, player=player, type="foul").count(),
                    exp["fouls"])
                self.assertEqual(Event.objects.filter(
                    match=self.match, player=player, type="card").count(),
                    exp["cards"])

    def test_assists_come_from_shot_rows(self):
        self.assertEqual(Shot.objects.filter(
            match=self.match, assist_player=self.players["H10"]).count(), 1)
        self.assertEqual(Shot.objects.filter(
            match=self.match, assist_player=self.players["H9"]).count(), 0)

    def test_player_xg_sums_to_shot_rows(self):
        for code in ("H9", "H10", "H7", "A9"):
            player = self.players[code]
            profile = get_player_profile_stats(player)
            row_sum = sum(s.xg for s in Shot.objects.filter(
                match=self.match, player=player))
            with self.subTest(player=code):
                self.assertAlmostEqual(profile["xg"], round(row_sum, 2), places=2)

    def test_player_progressive_passes(self):
        expected = {"H4": 1, "H10": 1, "H7": 1, "H9": 0, "A8": 1, "A11": 0}
        for code, count in expected.items():
            passing = get_player_passing_stats(self.players[code], match=self.match)
            with self.subTest(player=code):
                self.assertEqual(passing["progressive_passes"], count)


class EditReplayTest(TestCase):
    """Section 5: SAVED -> GOAL -> deleted, all state consistent."""

    def setUp(self):
        fresh_client(self)
        self.match, self.home, self.away, self.players = fx.make_fixture_match()
        self.events = fx.fixture_events(self.match, self.home, self.away, self.players)
        replay_stream(self.client, self.match, self.events)
        self.saved_event = Event.objects.get(match=self.match,
                                             external_event_id="FIX-S01")

    def _home_row(self):
        return MatchTeamStats.objects.get(match=self.match, team=self.home)

    def test_saved_to_goal_rebuilds_everything(self):
        keeper = self.players["A1"]
        shooter = self.players["H9"]
        before = self._home_row()
        self.assertEqual(before.goals, 1)  # FIX-S03 already scored
        home_xg_before = before.xg

        resp = self.client.patch(
            f"/api/match/{self.match.pk}/events/{self.saved_event.pk}/",
            {"payload": {"outcome": "goal"}}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)

        shot = Shot.objects.get(event_id=self.saved_event.pk)
        self.assertEqual(shot.outcome, "goal")
        self.assertTrue(shot.is_goal)
        self.assertGreater(shot.xg, 0)
        self.saved_event.refresh_from_db()
        self.assertEqual(self.saved_event.type, "goal")

        after = self._home_row()
        self.assertEqual(after.goals, 2)  # score changed 1 -> 2
        self.assertEqual(after.shots, before.shots)  # still one shot row
        self.assertEqual(after.shots_on_target, before.shots_on_target)
        self.assertAlmostEqual(after.xg, home_xg_before, places=3)
        self.assertEqual(get_player_profile_stats(shooter)["goals"], 2)

        # The keeper did not save a goal: linked save event is gone.
        self.assertFalse(Event.objects.filter(
            match=self.match, related_event_id=self.saved_event.pk).exists())
        self.assertEqual(Save.objects.filter(match=self.match,
                                             player=keeper).count(), 0)

    def test_delete_returns_to_pre_event_state(self):
        self.client.patch(
            f"/api/match/{self.match.pk}/events/{self.saved_event.pk}/",
            {"payload": {"outcome": "goal"}}, format="json")
        resp = self.client.delete(
            f"/api/match/{self.match.pk}/events/{self.saved_event.pk}/")
        self.assertEqual(resp.status_code, 204)

        after = self._home_row()
        exp = fx.EXPECTED_MATCH_TOTALS["home"]
        # Back to the fixture baseline minus the deleted saved shot.
        self.assertEqual(after.goals, 1)
        self.assertEqual(after.shots, exp["shots"] - 1)
        self.assertEqual(after.shots_on_target, exp["shots_on_target"] - 1)
        remaining_xg = sum(s.xg for s in Shot.objects.filter(
            match=self.match, team=self.home))
        self.assertAlmostEqual(after.xg, remaining_xg, places=3)
        self.assertEqual(get_player_profile_stats(
            self.players["H9"])["goals"], 1)
        self.assertFalse(Shot.objects.filter(
            event__external_event_id="FIX-S01").exists())


class IdempotencyTest(TestCase):
    """Sections 6, 8: same key replayed -> exactly one event, stable stats."""

    def setUp(self):
        fresh_client(self)
        self.match, self.home, self.away, self.players = fx.make_fixture_match()
        self.events = fx.fixture_events(self.match, self.home, self.away, self.players)

    def _post_all(self):
        statuses = []
        for spec in self.events:
            body = {k: v for k, v in spec.items() if k != "key"}
            resp = self.client.post(f"/api/match/{self.match.pk}/events/",
                                    body, format="json")
            statuses.append(resp.status_code)
        return statuses

    def _stats_snapshot(self):
        return {
            "events": Event.objects.filter(match=self.match).count(),
            "shots": Shot.objects.filter(match=self.match).count(),
            "home": MatchTeamStats.objects.get(
                match=self.match, team=self.home).__dict__,
            "away": MatchTeamStats.objects.get(
                match=self.match, team=self.away).__dict__,
        }

    def test_replay_same_match_with_same_keys_is_stable(self):
        first = self._post_all()
        self.assertTrue(all(s == 201 for s in first), first)
        snapshot = self._stats_snapshot()
        second = self._post_all()
        self.assertTrue(all(s == 200 for s in second), second)
        replayed = self._stats_snapshot()
        self.assertEqual(replayed["events"], snapshot["events"])
        self.assertEqual(replayed["shots"], snapshot["shots"])
        for side in ("home", "away"):
            for field in ("goals", "shots", "shots_on_target", "xg",
                          "passes", "completed_passes"):
                self.assertEqual(replayed[side][field], snapshot[side][field],
                                 f"{side}.{field}")

    def test_duplicate_goal_post_does_not_double_count(self):
        bodies = replay_stream(self.client, self.match, self.events)
        goal_body = next(s for s in self.events if s["key"] == "FIX-S03")
        body = {k: v for k, v in goal_body.items() if k != "key"}
        for _ in range(3):
            resp = self.client.post(f"/api/match/{self.match.pk}/events/",
                                    body, format="json")
            self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(Shot.objects.filter(match=self.match,
                                             is_goal=True).count(), 1)
        self.assertEqual(MatchTeamStats.objects.get(
            match=self.match, team=self.home).goals, 1)
        self.assertEqual(bodies["FIX-S03"]["id"],
                         Event.objects.get(match=self.match,
                                           external_event_id="FIX-S03").pk)


class ReplayTwiceTest(TestCase):
    """Section 8: identical streams on separate matches -> identical output."""

    def setUp(self):
        fresh_client(self)

    def test_two_matches_produce_identical_analytics(self):
        summaries = []
        for run in range(2):
            match, home, away, players = fx.make_fixture_match()
            events = fx.fixture_events(match, home, away, players)
            # external_event_id is globally unique: namespace keys per run,
            # exactly as two real matches would never share operator keys.
            for spec in events:
                key = spec["payload"]["external_event_id"]
                spec["payload"] = {**spec["payload"],
                                   "external_event_id": f"R{run}-{key}"}
            replay_stream(self.client, match, events)
            summary = fx.summarize_match(match)
            # Normalize DB-generated ids out of the comparison.
            summaries.append({
                "teams": summary["teams"],
                "players": summary["players"],
                "events": summary["match"]["event_count"],
            })
        self.assertEqual(summaries[0], summaries[1])


class InvariantsTest(TestCase):
    """Section 9: football invariants hold on the validated state."""

    def setUp(self):
        fresh_client(self)
        self.match, self.home, self.away, self.players = fx.make_fixture_match()
        replay_stream(self.client, self.match,
                      fx.fixture_events(self.match, self.home, self.away, self.players))

    def test_match_level_invariants(self):
        home = MatchTeamStats.objects.get(match=self.match, team=self.home)
        away = MatchTeamStats.objects.get(match=self.match, team=self.away)
        for row in (home, away):
            self.assertLessEqual(row.goals, row.shots)
            self.assertLessEqual(row.shots_on_target, row.shots)
            self.assertLessEqual(row.completed_passes, row.passes)
        home_passing = get_team_passing_stats(self.home, match=self.match)
        away_passing = get_team_passing_stats(self.away, match=self.match)
        for passing, row in ((home_passing, home), (away_passing, away)):
            self.assertLessEqual(passing["progressive_passes"], row.passes)
        # Entry flags are per-pass subsets.
        for prow in Pass.objects.filter(match=self.match):
            derived = prow.event.extra_data["derived"]
            self.assertLessEqual(int(derived["final_third_entry"]), 1)
            self.assertLessEqual(int(derived["penalty_area_entry"]), 1)

    def test_blocked_shots_subset(self):
        for team in (self.home, self.away):
            total = Shot.objects.filter(match=self.match, team=team).count()
            blocked = Shot.objects.filter(match=self.match, team=team,
                                          outcome="blocked").count()
            self.assertLessEqual(blocked, total)

    def test_player_team_goal_consistency(self):
        home = MatchTeamStats.objects.get(match=self.match, team=self.home)
        away = MatchTeamStats.objects.get(match=self.match, team=self.away)
        home_player_goals = sum(
            get_player_profile_stats(p)["goals"]
            for p in self.home.player_set.all())
        away_player_goals = sum(
            get_player_profile_stats(p)["goals"]
            for p in self.away.player_set.all())
        self.assertEqual(home_player_goals, home.goals)
        self.assertEqual(away_player_goals, away.goals)
        self.assertEqual(home.goals + away.goals, 1)

    def test_player_xg_sums_to_team_xg(self):
        for team, row_team in ((self.home, "home"), (self.away, "away")):
            row = MatchTeamStats.objects.get(match=self.match, team=team)
            player_xg = round(sum(
                get_player_profile_stats(p)["xg"]
                for p in team.player_set.all()), 4)
            self.assertAlmostEqual(player_xg, round(row.xg, 2), places=2)


class XgValidationTest(TestCase):
    """Section 10: xG comes from the pluggable calculator, never the client."""

    def setUp(self):
        fresh_client(self)
        self.match, self.home, self.away, self.players = fx.make_fixture_match()
        replay_stream(self.client, self.match,
                      fx.fixture_events(self.match, self.home, self.away, self.players))

    def _expected_xg(self, shot):
        return calculate_xg(ShotFeatures(
            x=shot.x, y=shot.y, body_part=shot.body_part,
            shot_type=shot.shot_type or "open_play"))

    def test_stored_xg_matches_calculator(self):
        for shot in Shot.objects.filter(match=self.match):
            with self.subTest(shot=shot.pk):
                self.assertAlmostEqual(shot.xg, self._expected_xg(shot), places=4)

    def test_client_xg_is_ignored(self):
        resp = self.client.post(
            f"/api/match/{self.match.pk}/events/",
            {"type": "shot", "period": 2, "minute": 80, "second": 0,
             "team": self.home.id, "player": self.players["H9"].id,
             "x": 60.0, "y": 40.0,
             "payload": {"outcome": "off_target", "xg": 0.99,
                         "external_event_id": "FIX-XG-PROBE"}},
            format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        shot = Shot.objects.get(event__external_event_id="FIX-XG-PROBE")
        self.assertNotEqual(shot.xg, 0.99)
        self.assertAlmostEqual(shot.xg, self._expected_xg(shot), places=4)
        resp = self.client.delete(
            f"/api/match/{self.match.pk}/events/{shot.event_id}/")
        self.assertEqual(resp.status_code, 204)

    def test_xg_ordering_and_bounds(self):
        xgs = {s.event.external_event_id: s.xg
               for s in Shot.objects.filter(match=self.match)}
        for key, value in xgs.items():
            self.assertGreater(value, 0, key)
            self.assertLess(value, 1, key)
        # Closest central shot has the highest xG; longest shot the lowest.
        self.assertEqual(max(xgs, key=xgs.get), "FIX-S03")
        self.assertEqual(min(xgs, key=xgs.get), "FIX-S05")

    def test_edit_location_changes_xg_and_delete_removes_it(self):
        event = Event.objects.get(match=self.match,
                                  external_event_id="FIX-S04")
        shot = event.shot_detail
        old_xg = shot.xg
        team_before = MatchTeamStats.objects.get(match=self.match,
                                                 team=self.away).xg
        # S04 is away's only shot: team xG equals its xG.
        self.assertAlmostEqual(team_before, old_xg, places=3)
        resp = self.client.patch(
            f"/api/match/{self.match.pk}/events/{event.pk}/",
            {"x": 112.0, "y": 40.0}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        shot.refresh_from_db()
        self.assertNotAlmostEqual(shot.xg, old_xg, places=4)
        self.assertGreater(shot.xg, old_xg)
        self.client.delete(f"/api/match/{self.match.pk}/events/{event.pk}/")
        team_after = MatchTeamStats.objects.get(match=self.match,
                                                team=self.away).xg
        # Deleting the only shot removes its whole contribution.
        self.assertAlmostEqual(team_after, 0.0, places=3)
        self.assertAlmostEqual(team_after, team_before - old_xg, places=3)

    def test_goal_has_single_xg_record(self):
        goal_shots = Shot.objects.filter(match=self.match, is_goal=True)
        self.assertEqual(goal_shots.count(), 1)
        home = MatchTeamStats.objects.get(match=self.match, team=self.home)
        home_shots_xg = sum(s.xg for s in Shot.objects.filter(
            match=self.match, team=self.home))
        self.assertAlmostEqual(home.xg, home_shots_xg, places=3)


class QueryBudgetTest(TestCase):
    """Section 11 (micro): one collection POST stays in a bounded query
    budget — guards against N+1 regressions on the hot path."""

    def setUp(self):
        fresh_client(self)
        self.match, self.home, self.away, self.players = fx.make_fixture_match()

    def test_single_create_query_budget(self):
        body = {"type": "pass", "period": 1, "minute": 1, "second": 0,
                "team": self.home.id, "player": self.players["H4"].id,
                "x": 30.0, "y": 40.0,
                "payload": {"end_x": 60.0, "end_y": 40.0, "outcome": "complete",
                            "external_event_id": "FIX-QB-1"}}
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.post(f"/api/match/{self.match.pk}/events/",
                                    body, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        # Measured at 33; the bound leaves headroom for validators while
        # catching full-table scans or per-row fan-out on this path.
        self.assertLess(len(ctx), 60, "\n".join(q["sql"][:120] for q in ctx))


class RebuildEquivalenceTest(TestCase):
    """Batch rebuild produces byte-identical analytics and stays correct
    across the edit/delete mutation chains."""

    def setUp(self):
        fresh_client(self)
        self.match, self.home, self.away, self.players = fx.make_fixture_match()
        self.events = fx.fixture_events(self.match, self.home, self.away, self.players)
        replay_stream(self.client, self.match, self.events)

    def test_explicit_rebuild_matches_live_output(self):
        from analytics.services.live_match_stats import rebuild_match_aggregates

        before = fx.summarize_match(self.match)
        with CaptureQueriesContext(connection) as ctx:
            rebuild_match_aggregates(self.match.pk)
        after = fx.summarize_match(self.match)
        self.assertEqual(before, after)
        # One zeroing update + one ordered load + detail prefetches + one
        # team-row read + one bulk write: independent of event count.
        self.assertLess(len(ctx), 15, "\n".join(q["sql"][:120] for q in ctx))

    def test_rebuild_idempotent(self):
        from analytics.services.live_match_stats import rebuild_match_aggregates

        rebuild_match_aggregates(self.match.pk)
        first = fx.summarize_match(self.match)
        rebuild_match_aggregates(self.match.pk)
        self.assertEqual(first, fx.summarize_match(self.match))

    def test_saved_to_goal_to_delete_chain(self):
        baseline = fx.summarize_match(self.match)
        saved = Event.objects.get(match=self.match,
                                  external_event_id="FIX-S01")

        resp = self.client.patch(
            f"/api/match/{self.match.pk}/events/{saved.pk}/",
            {"payload": {"outcome": "goal"}}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        edited = fx.summarize_match(self.match)
        self.assertEqual(edited["teams"][self.home.name]["goals"], 2)
        self.assertEqual(edited["players"]["H9"]["goals"], 2)
        # Same shot row, still counted once in every total.
        self.assertEqual(edited["teams"][self.home.name]["shots"], 4)
        self.assertEqual(
            edited["teams"][self.home.name]["shots_on_target"], 2)

        resp = self.client.delete(
            f"/api/match/{self.match.pk}/events/{saved.pk}/")
        self.assertEqual(resp.status_code, 204, resp.content)
        deleted = fx.summarize_match(self.match)
        home, away = self.home.name, self.away.name
        self.assertEqual(deleted["teams"][home]["goals"], 1)
        self.assertEqual(deleted["teams"][home]["shots"],
                         baseline["teams"][home]["shots"] - 1)
        self.assertEqual(deleted["teams"][home]["shots_on_target"],
                         baseline["teams"][home]["shots_on_target"] - 1)
        self.assertEqual(deleted["players"]["H9"]["goals"], 1)
        self.assertEqual(deleted["players"]["H9"]["shots"],
                         baseline["players"]["H9"]["shots"] - 1)
        self.assertFalse(Shot.objects.filter(event_id=saved.pk).exists())
        self.assertFalse(Event.objects.filter(
            match=self.match, related_event_id=saved.pk).exists())

    def test_pass_edit_and_delete_rebuild(self):
        baseline = fx.summarize_match(self.match)
        home = self.home.name
        event = Event.objects.get(match=self.match,
                                  external_event_id="FIX-P01")

        resp = self.client.patch(
            f"/api/match/{self.match.pk}/events/{event.pk}/",
            {"payload": {"outcome": "incomplete", "end_x": 35.0,
                         "end_y": 40.0}}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        edited = fx.summarize_match(self.match)
        self.assertEqual(edited["teams"][home]["completed_passes"],
                         baseline["teams"][home]["completed_passes"] - 1)
        self.assertEqual(edited["teams"][home]["passes"],
                         baseline["teams"][home]["passes"])
        # Shorter and non-progressive (goal-distance reduction 5 < 10).
        prow = Pass.objects.get(event_id=event.pk)
        self.assertAlmostEqual(prow.length, 5.0, places=1)
        self.assertFalse(prow.event.extra_data["derived"]["progressive"])
        self.assertEqual(edited["players"]["H4"]["completed_passes"], 0)

        resp = self.client.delete(
            f"/api/match/{self.match.pk}/events/{event.pk}/")
        self.assertEqual(resp.status_code, 204, resp.content)
        deleted = fx.summarize_match(self.match)
        self.assertEqual(deleted["teams"][home]["passes"],
                         baseline["teams"][home]["passes"] - 1)
        self.assertEqual(deleted["teams"][home]["completed_passes"],
                         baseline["teams"][home]["completed_passes"] - 1)
        self.assertFalse(Pass.objects.filter(event_id=event.pk).exists())
        self.assertEqual(deleted["players"]["H4"]["passes"], 0)
