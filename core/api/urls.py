"""API URL routing."""

from django.urls import path

from core.api.views import LiveMatchStatsView, LiveMatchView, EventCreateView, EventDetailView, MatchClockView


urlpatterns = [
    path("live-match/<path:match_id>", LiveMatchView.as_view(), name="api-live-match"),
    path("match/<path:match_id>/live-stats/", LiveMatchStatsView.as_view(), name="api-live-match-stats"),
    path("match/<int:match_id>/clock/", MatchClockView.as_view(), name="api-match-clock"),
    path("match/<path:match_id>/events/", EventCreateView.as_view(), name="api-event-create"),
    path("match/<path:match_id>/events/<int:event_id>/", EventDetailView.as_view(), name="api-event-detail"),
]
