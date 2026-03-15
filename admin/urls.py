from django.urls import path
from django.contrib.auth import views as auth_views
from admin.views.auth import RoleAwareLoginView
from admin.views.dashboard import dashboard
from admin.views.competition import  (
    competition_create,
    competition_delete,
    competition_list,
    competition_update
)
from admin.views.match import (
    match_create,
    match_delete,
    match_list,
    match_update,
)
from admin.views.player import (
    player_create,
    player_delete,
    player_list,
    player_update,
)
from admin.views.season import (
    season_create,
    season_delete,
    season_list,
    season_update,
)

from admin.views.stadium import (
    stadium_create,
    stadium_delete,
    stadium_list,
    stadium_update,
)

from admin.views.team import (
    team_create,
    team_delete,
    team_list,
    team_update,
)


urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("login", RoleAwareLoginView.as_view(), name='admin-login'),
    
    # teams
    path("teams/", team_list, name="team-list"),
    path("teams/add/", team_create, name="team-create"),
    path("teams/<int:pk>/edit/", team_update, name="team-update"),
    path("teams/<int:pk>/delete/", team_delete, name="team-delete"),

    # stadiums
    path("stadiums/", stadium_list, name="stadium-list"),
    path("stadiums/add/", stadium_create, name="stadium-create"),
    path("stadiums/<int:pk>/edit/", stadium_update, name="stadium-update"),
    path("stadiums/<int:pk>/delete/", stadium_delete, name="stadium-delete"),

    # players
    path("players/", player_list, name="player-list"),
    path("players/add/", player_create, name="player-create"),
    path("players/<int:pk>/edit/", player_update, name="player-update"),
    path("players/<int:pk>/delete/", player_delete, name="player-delete"),

    # competitions
    path("competitions/", competition_list, name="competition-list"),
    path("competitions/add/", competition_create, name="competition-create"),
    path("competitions/<int:pk>/edit/", competition_update, name="competition-update"),
    path("competitions/<int:pk>/delete/", competition_delete, name="competition-delete"),

    # seasons
    path("seasons/", season_list, name="season-list"),
    path("seasons/add/", season_create, name="season-create"),
    path("seasons/<int:pk>/edit/", season_update, name="season-update"),
    path("seasons/<int:pk>/delete/", season_delete, name="season-delete"),

    # matches
    path("matches/", match_list, name="match-list"),
    path("matches/add/", match_create, name="match-create"),
    path("matches/<int:pk>/edit/", match_update, name="match-update"),
    path("matches/<int:pk>/delete/", match_delete, name="match-delete"),
    
    #dashboard
    path("dashboard/", dashboard, name="dashboard-home"),
    
    path("logout", auth_views.LogoutView.as_view(), name='admin-logout')
]
