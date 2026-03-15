"""URL routing for futball app views."""

from django.urls import path
from core.views.home import home_view
from core.views.stats.dashboard import dashboard_view
from core.views.stats.xg import xg_pitch_map_view
from core.views.standings import league_table_view
from core.views.news import news_list, news_detail
from core.views.match import fixture_and_results, match_detail
from core.views.players import player_list, player_profile, player_stats

urlpatterns = [
    path("", home_view, name="home"),
    path("klasemen/", league_table_view, name="league-table"),
    path("stats/", dashboard_view, name="stats-dashboard"),
    path("xg-pitch/", xg_pitch_map_view, name="xg-pitch-map"),
    path("fixtures/", fixture_and_results, name="fixture-list"),
    path("fixtures/<path:match_id>/", match_detail, name="match-detail"),
    path("players/", player_list, name="player-list"),
    path("players/<int:player_id>/", player_profile, name="player-profile"),
    path("players/<int:player_id>/stats/", player_stats, name="player-stats"),
    path("news/", news_list, name="news_list"),
    path("news/<slug:slug>/", news_detail, name="news_detail"),
]
