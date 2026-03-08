"""URL routing for futball app views."""

from django.urls import path
from futball.views.home import home_view
from futball.views.stats.dashboard import dashboard_view
from futball.views.stats.xg import xg_pitch_map_view
from futball.views.standings import league_table_view
from futball.views.news import news_list, news_detail
from futball.views.match import fixture_and_results, match_detail

urlpatterns = [
    path("", home_view, name="home"),
    path("klasemen/", league_table_view, name="league-table"),
    path("stats/", dashboard_view, name="stats-dashboard"),
    path("xg-pitch/", xg_pitch_map_view, name="xg-pitch-map"),
    path("fixtures/", fixture_and_results, name="fixture-list"),
    path("fixtures/<path:match_id>/", match_detail, name="match-detail"),
    path("news/", news_list, name="news_list"),
    path("news/<slug:slug>/", news_detail, name="news_detail"),
]
