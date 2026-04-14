"""API URL routing."""

from django.urls import path

from core.api.views import LiveMatchStatsView, LiveMatchView


urlpatterns = [
    path("live-match/<path:match_id>", LiveMatchView.as_view(), name="api-live-match"),
    path("match/<path:match_id>/live-stats/", LiveMatchStatsView.as_view(), name="api-live-match-stats"),
]
