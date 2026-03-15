"""Service helpers for player-level metric aggregation."""

from django.db.models import Count, ExpressionWrapper, F, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce

from core.models.player_match import PlayerMatch
from core.models.shots import Shot


def get_player_profile_stats(player):
    """Return aggregate profile stats for a single player."""
    minutes_expression = ExpressionWrapper(
        F("minute_off") - F("minute_on"),
        output_field=IntegerField(),
    )
    player_matches = PlayerMatch.objects.filter(player=player)

    match_stats = player_matches.aggregate(
        matches=Count("id"),
        minutes_played=Coalesce(Sum(minutes_expression), Value(0)),
    )

    shot_stats = Shot.objects.filter(player=player).aggregate(
        shots=Count("id"),
        xg=Coalesce(Sum("xg"), Value(0.0)),
    )

    starts = player_matches.filter(is_starter=True).count()
    goals = Shot.objects.filter(player=player, is_goal=True).count()

    matches = match_stats["matches"] or 0
    minutes_played = match_stats["minutes_played"] or 0
    shots = shot_stats["shots"] or 0
    xg = shot_stats["xg"] or 0.0

    return {
        "matches": matches,
        "starts": starts,
        "minutes_played": max(minutes_played, 0),
        "shots": shots,
        "goals": goals,
        "xg": round(xg, 2),
        "shot_accuracy": round((goals / shots) * 100, 1) if shots else 0,
        "xg_per_shot": round(xg / shots, 2) if shots else 0,
        "minutes_per_goal": round(minutes_played / goals, 1) if goals else None,
        "goal_contribution_rate": round(goals / matches, 2) if matches else 0,
    }


def get_player_match_stats(player, limit=10):
    """Return recent per-match shot and minutes stats for a player."""
    rows = (
        PlayerMatch.objects.filter(player=player)
        .select_related("match", "team", "match__home_team", "match__away_team")
        .order_by("-match__match_date")[:limit]
    )

    match_ids = [row.match_id for row in rows]
    shot_rows = (
        Shot.objects.filter(player=player, match_id__in=match_ids)
        .values("match_id")
        .annotate(
            shots=Count("id"),
            goals=Count("id", filter=Q(is_goal=True)),
            xg=Coalesce(Sum("xg"), Value(0.0)),
        )
    )
    shot_map = {
        row["match_id"]: {
            "shots": row["shots"] or 0,
            "goals": row["goals"] or 0,
            "xg": round(row["xg"] or 0.0, 2),
        }
        for row in shot_rows
    }

    stats = []
    for row in rows:
        shot_stat = shot_map.get(
            row.match_id,
            {"shots": 0, "goals": 0, "xg": 0.0},
        )
        stats.append(
            {
                "match": row.match,
                "team": row.team,
                "minutes_played": max((row.minute_off or 0) - (row.minute_on or 0), 0),
                "is_starter": row.is_starter,
                "shots": shot_stat["shots"],
                "goals": shot_stat["goals"],
                "xg": shot_stat["xg"],
            }
        )

    return stats

