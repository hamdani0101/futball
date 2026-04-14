"""WebSocket consumers for live match updates."""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
from django.db.models import Prefetch

from analytics.services.live_dashboard import invalidate_live_stats_cache
from core.api.serializers import LiveMatchSerializer, RecentEventSerializer
from core.models.event import Event
from core.models.match import Match
from core.models.match_team_stat import MatchTeamStats


class LiveMatchConsumer(AsyncJsonWebsocketConsumer):
    """Broadcast live stats and event updates for one match."""

    async def connect(self):
        self.match_id = self.scope["url_route"]["kwargs"]["match_id"]
        self.group_name = live_match_group_name(self.match_id)

        if not await self._match_exists(self.match_id):
            await self.close(code=4404)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                "type": "live_match.snapshot",
                "data": await get_live_match_snapshot(self.match_id),
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def live_match_update(self, event):
        await self.send_json(
            {
                "type": "live_match.update",
                "data": event["data"],
            }
        )

    @database_sync_to_async
    def _match_exists(self, match_id):
        return Match.objects.filter(id=match_id).exists()


def broadcast_live_match_update(event: Event) -> None:
    """Send updated stats and the new event to the match WebSocket group."""
    channel_layer = get_channel_layer()
    invalidate_live_stats_cache(event.match_id)
    if channel_layer is None:
        return

    payload = {
        "match": get_live_match_snapshot_sync(event.match_id),
        "event": serialize_recent_event(event),
    }
    async_to_sync(channel_layer.group_send)(
        live_match_group_name(event.match_id),
        {
            "type": "live.match.update",
            "data": payload,
        },
    )


@database_sync_to_async
def get_live_match_snapshot(match_id):
    return get_live_match_snapshot_sync(match_id)


def get_live_match_snapshot_sync(match_id):
    """Return the same live match payload shape used by the REST endpoint."""
    match = (
        Match.objects.select_related("home_team", "away_team")
        .prefetch_related(
            Prefetch(
                "team_stats",
                queryset=MatchTeamStats.objects.select_related("team").only(
                    "id",
                    "match_id",
                    "team_id",
                    "team__id",
                    "team__name",
                    "score",
                    "possession",
                    "shots",
                    "shots_on_target",
                    "xg",
                    "passes",
                    "completed_passes",
                    "pass_accuracy",
                ),
                to_attr="_prefetched_team_stats",
            )
        )
        .only(
            "id",
            "external_id",
            "status",
            "period",
            "current_minute",
            "current_second",
            "home_team_id",
            "away_team_id",
            "home_team__name",
            "away_team__name",
        )
        .get(id=match_id)
    )
    recent_events = list(_recent_events_queryset().filter(match_id=match_id)[:20])
    return LiveMatchSerializer(
        match,
        context={"recent_events": recent_events},
    ).data


def serialize_recent_event(event: Event) -> dict:
    event = (
        _recent_events_queryset()
        .filter(pk=event.pk)
        .first()
        or event
    )
    return RecentEventSerializer(event).data


def live_match_group_name(match_id) -> str:
    return f"live_match_{match_id}"


def _recent_events_queryset():
    return (
        Event.objects.select_related(
            "team",
            "player",
            "shot_detail",
            "pass_detail",
            "pass_detail__recipient",
            "substitution_detail",
            "substitution_detail__player_out",
            "substitution_detail__player_in",
        )
        .order_by("-period", "-minute", "-second", "-event_index", "-id")
    )
