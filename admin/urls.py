from django.urls import path

from .views import (
    dashboard,
    match_create,
    match_delete,
    match_list,
    match_update,
    player_create,
    player_delete,
    player_list,
    player_update,
    team_create,
    team_delete,
    team_list,
    team_update,
)


urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("teams/", team_list, name="team-list"),
    path("teams/add/", team_create, name="team-create"),
    path("teams/<int:pk>/edit/", team_update, name="team-update"),
    path("teams/<int:pk>/delete/", team_delete, name="team-delete"),
    path("players/", player_list, name="player-list"),
    path("players/add/", player_create, name="player-create"),
    path("players/<int:pk>/edit/", player_update, name="player-update"),
    path("players/<int:pk>/delete/", player_delete, name="player-delete"),
    path("matches/", match_list, name="match-list"),
    path("matches/add/", match_create, name="match-create"),
    path("matches/<int:pk>/edit/", match_update, name="match-update"),
    path("matches/<int:pk>/delete/", match_delete, name="match-delete"),
    path("dashboard/", dashboard, name="dashboard-home"),
]
