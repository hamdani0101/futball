"""Views for live match dashboard API endpoints."""

from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.services.live_dashboard import get_live_stats_payload
from core.api.serializers import LiveMatchSerializer
from core.models.event import Event
from core.models.match import Match
from core.models.match_team_stat import MatchTeamStats


from rest_framework import status
from django.db import transaction
from core.api.serializers import LiveMatchSerializer, EventCreateSerializer, RecentEventSerializer

class EventCreateView(APIView):
    """Create a new match event and associated details (Shot, Pass, etc)."""

    @transaction.atomic
    def post(self, request, match_id):
        from analytics.services.match_clock import collection_blocked_reason
        from core.consumers import schedule_broadcast
        from django.db import IntegrityError

        match = get_object_or_404(Match, pk=match_id)
        blocked = collection_blocked_reason(match)
        if blocked:
            return Response({"detail": blocked}, status=status.HTTP_400_BAD_REQUEST)
        serializer = EventCreateSerializer(data=request.data, context={'match': match})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        # Client retries share one external_event_id per form session; a
        # retried POST must return the original row, never a duplicate.
        idempotency_key = (request.data.get('payload') or {}).get('external_event_id')
        if idempotency_key:
            existing = Event.objects.filter(
                match_id=match.pk, external_event_id=idempotency_key
            ).first()
            if existing:
                return Response(RecentEventSerializer(existing).data,
                                status=status.HTTP_200_OK)
        try:
            with transaction.atomic():
                event = serializer.save()
        except IntegrityError:
            existing = Event.objects.filter(
                match_id=match.pk, external_event_id=idempotency_key
            ).first()
            if existing:
                return Response(RecentEventSerializer(existing).data,
                                status=status.HTTP_200_OK)
            raise
        schedule_broadcast(match.pk, kind="created", event=event)
        return Response(RecentEventSerializer(event).data, status=status.HTTP_201_CREATED)

class EventDetailView(APIView):
    """Edit, delete or fetch a single event."""

    @transaction.atomic
    def patch(self, request, match_id, event_id):
        from analytics.services.derived import derive_pass_metrics, derive_shot_metrics
        from analytics.services.live_match_stats import rebuild_match_aggregates
        from core.consumers import schedule_broadcast
        from core.models.player import Player
        from core.models.shots import Shot
        from core.models.team import Team

        event = get_object_or_404(Event, pk=event_id, match_id=match_id)
        match = event.match
        payload = request.data.get('payload', {}) or {}
        data = request.data

        # Optional human-field corrections, validated like creation.
        if 'team' in data and data['team'] is not None:
            try:
                team = Team.objects.get(pk=int(data['team']))
            except (Team.DoesNotExist, TypeError, ValueError):
                return Response({"detail": "Selected team does not exist."},
                                status=status.HTTP_400_BAD_REQUEST)
            if team.id not in [match.home_team_id, match.away_team_id]:
                return Response({"detail": "Team must participate in this match."},
                                status=status.HTTP_400_BAD_REQUEST)
            event.team = team
        if 'player' in data:
            if data['player'] in (None, ''):
                event.player = None
            else:
                try:
                    player = Player.objects.get(pk=int(data['player']))
                except (Player.DoesNotExist, TypeError, ValueError):
                    return Response({"detail": "Selected player does not exist."},
                                    status=status.HTTP_400_BAD_REQUEST)
                if player.team_now_id != event.team_id:
                    return Response({"detail": "Player does not belong to selected team."},
                                    status=status.HTTP_400_BAD_REQUEST)
                event.player = player
        for axis, limit in (('x', 120), ('y', 80)):
            if axis in data and data[axis] is not None:
                try:
                    value = float(data[axis])
                except (TypeError, ValueError):
                    return Response({"detail": f"Shot location is outside the pitch."},
                                    status=status.HTTP_400_BAD_REQUEST)
                if not (0 <= value <= limit):
                    return Response({"detail": "Shot location is outside the pitch."},
                                    status=status.HTTP_400_BAD_REQUEST)
                setattr(event, axis, value)
        event.save()

        # Recalculate derived metrics so aggregates never go stale.
        if hasattr(event, 'shot_detail') and event.shot_detail is not None:
            shot = event.shot_detail
            if 'outcome' in payload:
                shot.outcome = payload['outcome']
                shot.is_goal = payload['outcome'] == 'goal'
                if payload['outcome'] == 'goal':
                    event.type = Event.Type.GOAL
                    event.save(update_fields=['type', 'updated_at'])
                elif event.type == Event.Type.GOAL:
                    event.type = Event.Type.SHOT
                    event.save(update_fields=['type', 'updated_at'])
            if 'body_part' in payload:
                shot.body_part = payload['body_part']
            shot.team = event.team
            shot.player = event.player
            shot.x = event.x or 0
            shot.y = event.y or 0
            if event.x is not None and event.y is not None:
                derived = derive_shot_metrics(
                    event.x, event.y,
                    body_part=shot.body_part, shot_type=shot.shot_type,
                )
                shot.xg = derived['xg']
                shot.shot_distance = derived['distance']
                shot.shot_angle = derived['angle']
                shot.is_big_chance = derived['is_big_chance']
                event.extra_data = {
                    **(event.extra_data or {}),
                    'derived': {
                        'distance': derived['distance'],
                        'angle': derived['angle'],
                        'zone': derived['zone'],
                        'xg': derived['xg'],
                    },
                }
                event.save(update_fields=['extra_data', 'updated_at'])
            shot.save()
        # A save linked to a shot that is no longer saved (e.g. corrected to
        # a goal) contradicts the event stream; remove it like the delete
        # path does so rebuilds never see phantom saves.
        if payload.get('outcome') not in (None, Shot.Outcome.SAVED):
            Event.objects.filter(
                match_id=event.match_id,
                related_event_id=event.pk,
                type=Event.Type.SAVE,
            ).delete()
        if hasattr(event, 'pass_detail') and event.pass_detail is not None:
            prow = event.pass_detail
            if 'outcome' in payload:
                prow.outcome = payload['outcome']
            if 'end_x' in payload:
                prow.end_x = payload['end_x']
            if 'end_y' in payload:
                prow.end_y = payload['end_y']
            prow.team = event.team
            prow.player = event.player
            prow.x = event.x or 0
            prow.y = event.y or 0
            derived = derive_pass_metrics(prow.x, prow.y, prow.end_x, prow.end_y)
            prow.length = derived['length']
            prow.angle = derived['angle']
            prow.save()
            event.extra_data = {
                **(event.extra_data or {}),
                'derived': derived,
            }
            event.save(update_fields=['extra_data', 'updated_at'])
        if hasattr(event, 'substitution_detail') and event.substitution_detail is not None:
            sub = event.substitution_detail
            if 'player_out_id' in payload:
                sub.player_out_id = payload['player_out_id']
            if 'player_in_id' in payload:
                sub.player_in_id = payload['player_in_id']
            if (sub.player_in_id and sub.player_out_id
                    and sub.player_in_id == sub.player_out_id):
                return Response(
                    {"detail": "Substitution players must be different."},
                    status=status.HTTP_400_BAD_REQUEST)
            sub.team = event.team
            sub.save()
        # Outcome/location edits change totals → rebuild this match only.
        rebuild_match_aggregates(event.match_id)
        event = Event.objects.select_related(
            'team', 'player', 'shot_detail', 'pass_detail', 'pass_detail__recipient',
        ).get(pk=event.pk)
        # Corrections stay available at full time; aggregates + clients refresh.
        schedule_broadcast(event.match_id, kind="edited", event=event)
        return Response(RecentEventSerializer(event).data)

    @transaction.atomic
    def delete(self, request, match_id, event_id):
        from analytics.services.live_match_stats import rebuild_match_aggregates
        from core.consumers import schedule_broadcast

        event = get_object_or_404(Event, pk=event_id, match_id=match_id)
        match_pk = event.match_id
        deleted_id = event.pk
        # Detail rows use SET_NULL toward Event, so remove them explicitly —
        # otherwise ghost Shot/Pass/Substitution rows outlive their event.
        # Linked save events (auto-created from a saved shot) go with it;
        # their Save rows cascade, and stray originating_shot FKs null out.
        for relation in ("shot_detail", "pass_detail", "substitution_detail"):
            detail = getattr(event, relation, None)
            if detail is not None:
                detail.delete()
        Event.objects.filter(match_id=match_pk, related_event_id=event.pk).delete()
        event.delete()
        # Rebuild team aggregates from the remaining event stream (this match only).
        rebuild_match_aggregates(match_pk)
        schedule_broadcast(match_pk, kind="deleted", event_id=deleted_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

class LiveMatchView(APIView):
    RECENT_EVENT_LIMIT = 20

    def get(self, request, match_id):
        match = get_object_or_404(self.get_match_queryset(), self._match_lookup(match_id))
        recent_events = list(
            Event.objects.filter(match=match)
            .select_related(
                "team",
                "player",
                "shot_detail",
                "pass_detail",
                "pass_detail__recipient",
                "substitution_detail",
                "substitution_detail__player_out",
                "substitution_detail__player_in",
            )
            .order_by("-period", "-minute", "-second", "-event_index", "-id")[
                : self.RECENT_EVENT_LIMIT
            ]
        )

        serializer = LiveMatchSerializer(
            match,
            context={"request": request, "recent_events": recent_events},
        )
        return Response(serializer.data)

    def get_match_queryset(self):
        team_stats = (
            MatchTeamStats.objects.select_related("team")
            .only(
                "id",
                "match_id",
                "team_id",
                "team__id",
                "team__name",
                "goals",
                "possession",
                "shots",
                "shots_on_target",
                "xg",
                "passes",
                "completed_passes",
                "pass_accuracy",
            )
        )

        return (
            Match.objects.select_related("home_team", "away_team")
            .prefetch_related(
                Prefetch(
                    "team_stats",
                    queryset=team_stats,
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
        )

    @staticmethod
    def _match_lookup(match_id):
        try:
            numeric_match_id = int(match_id)
        except (TypeError, ValueError):
            return Q(external_id__isnull=True) & Q(pk__isnull=True)

        return Q(pk=numeric_match_id) | Q(external_id=numeric_match_id)


class LiveMatchStatsView(APIView):
    """Return aggregated live stats for one match."""

    def get(self, request, match_id):
        match = get_object_or_404(Match.objects.only("id", "external_id"), LiveMatchView._match_lookup(match_id))
        return Response(get_live_stats_payload(match.id))


class MatchClockView(APIView):
    """Server-authoritative clock state and transitions.

    GET returns the current clock, display state and available actions.
    POST {"action": "start_match" | "half_time" | "start_second_half" | "full_time"}
    applies a server-validated transition and notifies connected clients.
    """

    def get(self, request, match_id):
        from analytics.services.match_clock import available_actions, clock_payload

        match = get_object_or_404(Match, pk=match_id)
        payload = clock_payload(match)
        payload["available_actions"] = available_actions(match)
        return Response(payload)

    @transaction.atomic
    def post(self, request, match_id):
        from analytics.services.match_clock import (
            VALID_ACTIONS,
            available_actions,
            clock_payload,
            transition,
        )
        from core.consumers import schedule_broadcast

        match = get_object_or_404(Match, pk=match_id)
        action = (request.data.get("action") or "").strip()
        if action not in VALID_ACTIONS:
            return Response(
                {"detail": f"Unknown clock action. Use one of: {', '.join(VALID_ACTIONS)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            transition(match, action)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        schedule_broadcast(match.pk, kind="clock")
        payload = clock_payload(match)
        payload["available_actions"] = available_actions(match)
        return Response(payload)
