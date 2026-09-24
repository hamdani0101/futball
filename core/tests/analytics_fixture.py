"""Deterministic analytics-validation fixture: Redvale Rovers vs Blueport United.

No random data. Every event below is hand-specified; every expected total is
hand-derived from the production business rules:

- progressive pass: complete pass reducing goal-distance by >= 10
  (analytics.services.passing / derived.is_progressive_pass).
- final-third entry: start x < 80 <= end x (derived.is_final_third_entry).
- penalty-area entry: end x >= 102.5 and 18 <= end y <= 62
  (derived.is_penalty_area_entry).
- on target: outcome in {goal, saved, saved_off_target}
  (live_match_stats.ON_TARGET_SHOT_OUTCOMES).
- goals count shots + on-target + xG + goals exactly once via their own
  shot_detail (live_match_stats / event_processor GOAL branches).

Per-pass hand-derived flags (start -> end, goal-distance reduction):
  P01 (30,40)->(55,40): 90.00 -> 65.00 = 25.00  progressive=True
  P02 (55,40)->(85,50): 65.00 -> 36.40 = 28.60  progressive=True
  P03 (85,50)->(104,40): 36.40 -> 16.00 = 20.40 progressive=True
  P04 (104,40)->(90,30): 16.00 -> 31.62 = -15.62 progressive=False
  P05 (40,30)->(60,30): 80.62 -> 60.83 = 19.79  progressive=True
  P06 (60,30)->(95,40): 60.83 -> 25.00 = 35.83  progressive=True (flag only;
      incomplete, so excluded from the completed-pass service count).
"""

from django.utils import timezone

from core.models import Match, Player, Season, Team
from core.models.competition import Competition

HOME_NAME = "Redvale Rovers"
AWAY_NAME = "Blueport United"


def make_fixture_match():
    """Create a scratch match with explicitly named squads. No statistics."""
    competition = Competition.objects.create(name="Validation League", code="VLD")
    season = Season.objects.create(competition=competition, name="2026-validation")
    home = Team.objects.create(name=HOME_NAME)
    away = Team.objects.create(name=AWAY_NAME)
    players = {}
    for team, prefix in ((home, "H"), (away, "A")):
        for shirt in (1, 2, 4, 7, 8, 9, 10, 11):
            if prefix == "H" and shirt not in (1, 2, 4, 7, 9, 10):
                continue
            if prefix == "A" and shirt not in (1, 4, 8, 9, 11):
                continue
            code = f"{prefix}{shirt}"
            players[code] = Player.objects.create(name=code, team_now=team)
    match = Match.objects.create(
        season=season,
        home_team=home,
        away_team=away,
        match_date=timezone.now(),
    )
    return match, home, away, players


def fixture_events(match, home, away, players):
    """The deterministic event stream. Each dict is an API POST body with a
    fixed external_event_id, in chronological order."""
    P = players
    H = home.id
    A = away.id
    return [
        # --- passes (home build-up) ---
        {"key": "FIX-P01", "type": "pass", "period": 1, "minute": 5, "second": 10,
         "team": H, "player": P["H4"].id, "x": 30.0, "y": 40.0,
         "payload": {"end_x": 55.0, "end_y": 40.0, "outcome": "complete",
                     "recipient_id": P["H10"].id, "external_event_id": "FIX-P01"}},
        {"key": "FIX-P02", "type": "pass", "period": 1, "minute": 5, "second": 31,
         "team": H, "player": P["H10"].id, "x": 55.0, "y": 40.0,
         "payload": {"end_x": 85.0, "end_y": 50.0, "outcome": "complete",
                     "recipient_id": P["H7"].id, "external_event_id": "FIX-P02"}},
        {"key": "FIX-P03", "type": "pass", "period": 1, "minute": 6, "second": 2,
         "team": H, "player": P["H7"].id, "x": 85.0, "y": 50.0,
         "payload": {"end_x": 104.0, "end_y": 40.0, "outcome": "complete",
                     "recipient_id": P["H9"].id, "external_event_id": "FIX-P03"}},
        {"key": "FIX-P04", "type": "pass", "period": 1, "minute": 6, "second": 20,
         "team": H, "player": P["H9"].id, "x": 104.0, "y": 40.0,
         "payload": {"end_x": 90.0, "end_y": 30.0, "outcome": "incomplete",
                     "external_event_id": "FIX-P04"}},
        # --- away passes ---
        {"key": "FIX-P05", "type": "pass", "period": 1, "minute": 12, "second": 0,
         "team": A, "player": P["A8"].id, "x": 40.0, "y": 30.0,
         "payload": {"end_x": 60.0, "end_y": 30.0, "outcome": "complete",
                     "recipient_id": P["A11"].id, "external_event_id": "FIX-P05"}},
        {"key": "FIX-P06", "type": "pass", "period": 1, "minute": 12, "second": 25,
         "team": A, "player": P["A11"].id, "x": 60.0, "y": 30.0,
         "payload": {"end_x": 95.0, "end_y": 40.0, "outcome": "incomplete",
                     "external_event_id": "FIX-P06"}},
        # --- shots ---
        {"key": "FIX-S01", "type": "shot", "period": 1, "minute": 23, "second": 14,
         "team": H, "player": P["H9"].id, "x": 108.0, "y": 40.0,
         "payload": {"outcome": "saved", "body_part": "right_foot",
                     "save_player_id": P["A1"].id, "external_event_id": "FIX-S01"}},
        {"key": "FIX-S02", "type": "shot", "period": 1, "minute": 31, "second": 40,
         "team": H, "player": P["H10"].id, "x": 95.0, "y": 55.0,
         "payload": {"outcome": "blocked", "body_part": "right_foot",
                     "external_event_id": "FIX-S02"}},
        {"key": "FIX-S03", "type": "goal", "period": 2, "minute": 58, "second": 5,
         "team": H, "player": P["H9"].id, "x": 112.0, "y": 38.0,
         "payload": {"body_part": "right_foot",
                     "assist_player_id": P["H10"].id,
                     "external_event_id": "FIX-S03"}},
        # --- foul / card / substitution (64'-70', chronological) ---
        {"key": "FIX-F01", "type": "foul", "period": 2, "minute": 64, "second": 10,
         "team": A, "player": P["A4"].id, "x": 70.0, "y": 40.0,
         "payload": {"external_event_id": "FIX-F01"}},
        {"key": "FIX-C01", "type": "card", "period": 2, "minute": 64, "second": 12,
         "team": A, "player": P["A4"].id, "x": 70.0, "y": 40.0,
         "payload": {"card": "yellow", "external_event_id": "FIX-C01"}},
        {"key": "FIX-U01", "type": "substitution", "period": 2, "minute": 70,
         "second": 0, "team": H, "player": None, "x": 60.0, "y": 40.0,
         "payload": {"player_out_id": P["H7"].id, "player_in_id": P["H2"].id,
                     "reason": "tactical", "external_event_id": "FIX-U01"}},
        {"key": "FIX-S04", "type": "shot", "period": 2, "minute": 71, "second": 22,
         "team": A, "player": P["A9"].id, "x": 100.0, "y": 30.0,
         "payload": {"outcome": "off_target", "body_part": "left_foot",
                     "external_event_id": "FIX-S04"}},
        {"key": "FIX-S05", "type": "shot", "period": 2, "minute": 77, "second": 50,
         "team": H, "player": P["H7"].id, "x": 60.0, "y": 40.0,
         "payload": {"outcome": "wayward", "body_part": "head",
                     "external_event_id": "FIX-S05"}},
    ]


# Hand-derived expectations (see module docstring for the math).
EXPECTED_PASS_FLAGS = {
    # key: (progressive_flag, final_third_flag, penalty_area_flag, length)
    "FIX-P01": (True, False, False, 25.00),
    "FIX-P02": (True, True, False, 31.62),
    "FIX-P03": (True, False, True, 21.47),
    "FIX-P04": (False, False, False, 17.20),
    "FIX-P05": (True, False, False, 20.00),
    "FIX-P06": (True, True, False, 36.40),
}

EXPECTED_MATCH_TOTALS = {
    # team goals, shots, on-target, off-target outcomes, blocked, saves-linked
    "home": {"goals": 1, "shots": 4, "shots_on_target": 2,
             "off_target": 0, "wayward": 1, "blocked": 1, "saved": 1,
             "passes": 4, "completed_passes": 3, "incomplete_passes": 1,
             "progressive_passes": 3, "final_third_entries": 1,
             "penalty_area_entries": 1, "fouls": 0, "cards": 0, "saves": 0},
    "away": {"goals": 0, "shots": 1, "shots_on_target": 0,
             "off_target": 1, "wayward": 0, "blocked": 0, "saved": 0,
             "passes": 2, "completed_passes": 1, "incomplete_passes": 1,
             "progressive_passes": 1, "final_third_entries": 1,
             "penalty_area_entries": 0, "fouls": 1, "cards": 1, "saves": 1},
}

EXPECTED_PLAYER_TOTALS = {
    # shots, goals, assists, passes, completed, saves, fouls, cards
    "H9": {"shots": 2, "goals": 1, "assists": 0, "passes": 1, "completed": 0,
           "saves": 0, "fouls": 0, "cards": 0},
    "H10": {"shots": 1, "goals": 0, "assists": 1, "passes": 1, "completed": 1,
            "saves": 0, "fouls": 0, "cards": 0},
    "H7": {"shots": 1, "goals": 0, "assists": 0, "passes": 1, "completed": 1,
           "saves": 0, "fouls": 0, "cards": 0},
    "H4": {"shots": 0, "goals": 0, "assists": 0, "passes": 1, "completed": 1,
           "saves": 0, "fouls": 0, "cards": 0},
    "H2": {"shots": 0, "goals": 0, "assists": 0, "passes": 0, "completed": 0,
           "saves": 0, "fouls": 0, "cards": 0},
    "A9": {"shots": 1, "goals": 0, "assists": 0, "passes": 0, "completed": 0,
           "saves": 0, "fouls": 0, "cards": 0},
    "A8": {"shots": 0, "goals": 0, "assists": 0, "passes": 1, "completed": 1,
           "saves": 0, "fouls": 0, "cards": 0},
    "A11": {"shots": 0, "goals": 0, "assists": 0, "passes": 1, "completed": 0,
            "saves": 0, "fouls": 0, "cards": 0},
    "A1": {"shots": 0, "goals": 0, "assists": 0, "passes": 0, "completed": 0,
           "saves": 1, "fouls": 0, "cards": 0},
    "A4": {"shots": 0, "goals": 0, "assists": 0, "passes": 0, "completed": 0,
           "saves": 0, "fouls": 1, "cards": 1},
}

EXPECTED_EVENT_COUNT = 15  # 6 passes + 4 shots + 1 goal + 1 save + foul + card + sub
EXPECTED_SAVE_COUNT = 1


def summarize_match(match):
    """Collect every analytics output for a match into one comparable dict."""
    from analytics.services.passing import (
        get_player_passing_stats,
        get_team_passing_stats,
    )
    from analytics.services.player_metrics import get_player_profile_stats

    summary = {"teams": {}, "players": {}, "match": {}}
    for team in (match.home_team, match.away_team):
        row = match.team_stats.get(team=team)
        team_passing = get_team_passing_stats(team, match=match)
        summary["teams"][team.name] = {
            "goals": row.goals,
            "shots": row.shots,
            "shots_on_target": row.shots_on_target,
            "xg": round(row.xg or 0.0, 4),
            "passes": row.passes,
            "completed_passes": row.completed_passes,
            "pass_accuracy": row.pass_accuracy,
            "progressive_passes": team_passing["progressive_passes"],
        }
        for player in team.player_set.order_by("id"):
            profile = get_player_profile_stats(player)
            passing = get_player_passing_stats(player, match=match)
            summary["players"][player.name] = {
                "shots": profile["shots"],
                "goals": profile["goals"],
                "xg": profile["xg"],
                "passes": passing["passes"],
                "completed_passes": passing["completed_passes"],
                "progressive_passes": passing["progressive_passes"],
            }
    summary["match"]["event_count"] = match.events.count()
    return summary
