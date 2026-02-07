from django.urls import path
from futball.views.dashboard import dashboard_view
from futball.views.standings import league_table_view
from futball.views.xg import xg_map_view, xg_pitch_map_view

urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("klasemen/", league_table_view, name="league-table"),
    path("xg/", xg_map_view, name="xg-map"),
    path("xg-pitch/", xg_pitch_map_view, name="xg-pitch-map"),
]


