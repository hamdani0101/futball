"""URL routing for futball app views."""

from django.urls import path
from futball.views.dashboard import dashboard_view
from futball.views.standings import league_table_view
from futball.views.xg import xg_map_view, xg_pitch_map_view
from futball.views.news import news_list, news_detail
from futball.views.match import fixture_and_results, match_detail

urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("klasemen/", league_table_view, name="league-table"),
    path("xg/", xg_map_view, name="xg-map"),
    path("xg-pitch/", xg_pitch_map_view, name="xg-pitch-map"),
    path("fixtures/", fixture_and_results, name="fixture-list"),
    path("fixtures/<str:match_id>/", match_detail, name="match-detail"),
    path("news/", news_list, name="news_list"),
    path("news/<slug:slug>/", news_detail, name="news_detail"),
]

