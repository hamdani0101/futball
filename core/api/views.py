"""Views for live match dashboard API endpoints."""

from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.serializers import LiveMatchSerializer
from core.models.event import Event
from core.models.match import Match
from core.models.match_team_stat import MatchTeamStats


class LiveMatchView(APIView):
    """Return live score, stats, and recent events for one match."""

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
                "score",
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
