from django.urls import path
from .views import league_table_view, dashboard_view, xg_map_view

urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("table/", league_table_view, name="league-table"),
    path("xg/", xg_map_view, name="xg-map"),
]


