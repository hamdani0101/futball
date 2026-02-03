from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("klasemen/", views.league_table_view, name="league-table"),
    path("xg/", views.xg_map_view, name="xg-map"),
    path("xg-pitch/", views.xg_pitch_map_view, name="xg-pitch-map"),
]


