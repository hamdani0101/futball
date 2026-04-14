"""Aggregated live dashboard payloads for match statistics."""

from __future__ import annotations

from django.core.cache import cache
from django.db.models import Prefetch

from core.models.match import Match
from core.models.match_team_stat import MatchTeamStats


LIVE_STATS_CACHE_TTL_SECONDS = 15


def get_live_stats_payload(match_id: int) -> dict:
    """Return cached aggregated live stats for one match."""
    cache_key = _cache_key(match_id)
    cached_payload = cache.get(cache_key)
    if cached_payload is not None:
        return cached_payload

    match = (
        Match.objects.select_related("home_team", "away_team")
        .prefetch_related(
            Prefetch(
                "team_stats",
                queryset=MatchTeamStats.objects.select_related("team").only(
                    "match_id",
                    "team_id",
                    "team__name",
                    "possession",
                    "xg",
                    "shots",
                    "passes",
                    "completed_passes",
                ),
                to_attr="_prefetched_team_stats",
            )
        )
        .only(
            "id",
            "home_team_id",
            "away_team_id",
            "home_team__name",
            "away_team__name",
        )
        .get(pk=match_id)
    )

    stats_by_team = {
        stats.team_id: stats
        for stats in getattr(match, "_prefetched_team_stats", [])
    }
    ordered_teams = (
        (match.home_team_id, match.home_team.name),
        (match.away_team_id, match.away_team.name),
    )

    payload = {
        "possession": {},
        "xg": {},
        "shots": {},
        "passes": {},
    }

    for team_id, team_name in ordered_teams:
        stats = stats_by_team.get(team_id)
        payload["possession"][team_name] = int(stats.possession) if stats else 0
        payload["xg"][team_name] = round(float(stats.xg or 0.0), 4) if stats else 0.0
        payload["shots"][team_name] = int(stats.shots) if stats else 0
        payload["passes"][team_name] = {
            "total": int(stats.passes) if stats else 0,
            "completed": int(stats.completed_passes) if stats else 0,
        }

    cache.set(cache_key, payload, LIVE_STATS_CACHE_TTL_SECONDS)
    return payload


def invalidate_live_stats_cache(match_id: int) -> None:
    """Clear one match live-stats cache entry after a live update."""
    cache.delete(_cache_key(match_id))


def _cache_key(match_id: int) -> str:
    return f"api:match:{match_id}:live-stats"
