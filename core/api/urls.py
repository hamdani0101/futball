"""API URL routing."""

from django.urls import path

from core.api.views import LiveMatchView


urlpatterns = [
    path("live-match/<path:match_id>", LiveMatchView.as_view(), name="api-live-match"),
]
