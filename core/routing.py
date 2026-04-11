"""WebSocket routing for the core app."""

from django.urls import re_path

from core.consumers import LiveMatchConsumer


websocket_urlpatterns = [
    re_path(r"^ws/live-match/(?P<match_id>\d+)/$", LiveMatchConsumer.as_asgi()),
]
