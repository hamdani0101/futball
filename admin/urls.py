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
from admin.views.match_team_stat import (
    match_team_stat_create,
    match_team_stat_delete,
    match_team_stat_list,
    match_team_stat_update,
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
from admin.views.shot import (
    shot_create,
    shot_delete,
    shot_list,
    shot_update,
)


urlpatterns = [
    #dashboard
    path("", dashboard, name="admin-dashboard"),
    path("login", RoleAwareLoginView.as_view(), name='admin-login'),
    
    # teams
    path("teams/", team_list, name="admin-team-list"),
    path("teams/add/", team_create, name="admin-team-create"),
    path("teams/<int:pk>/edit/", team_update, name="admin-team-update"),
    path("teams/<int:pk>/delete/", team_delete, name="admin-team-delete"),

    # stadiums
    path("stadiums/", stadium_list, name="admin-stadium-list"),
    path("stadiums/add/", stadium_create, name="admin-stadium-create"),
    path("stadiums/<int:pk>/edit/", stadium_update, name="admin-stadium-update"),
    path("stadiums/<int:pk>/delete/", stadium_delete, name="admin-stadium-delete"),

    # players
    path("players/", player_list, name="admin-player-list"),
    path("players/add/", player_create, name="admin-player-create"),
    path("players/<int:pk>/edit/", player_update, name="admin-player-update"),
    path("players/<int:pk>/delete/", player_delete, name="admin-player-delete"),

    # competitions
    path("competitions/", competition_list, name="admin-competition-list"),
    path("competitions/add/", competition_create, name="admin-competition-create"),
    path("competitions/<int:pk>/edit/", competition_update, name="admin-competition-update"),
    path("competitions/<int:pk>/delete/", competition_delete, name="admin-competition-delete"),

    # seasons
    path("seasons/", season_list, name="admin-season-list"),
    path("seasons/add/", season_create, name="admin-season-create"),
    path("seasons/<int:pk>/edit/", season_update, name="admin-season-update"),
    path("seasons/<int:pk>/delete/", season_delete, name="admin-season-delete"),

    # matches
    path("matches/", match_list, name="admin-match-list"),
    path("matches/add/", match_create, name="admin-match-create"),
    path("matches/<int:pk>/edit/", match_update, name="admin-match-update"),
    path("matches/<int:pk>/delete/", match_delete, name="admin-match-delete"),

    # match stats
    path("match-stats/", match_team_stat_list, name="admin-match-stat-list"),
    path("match-stats/add/", match_team_stat_create, name="admin-match-stat-create"),
    path("match-stats/<int:pk>/edit/", match_team_stat_update, name="admin-match-stat-update"),
    path("match-stats/<int:pk>/delete/", match_team_stat_delete, name="admin-match-stat-delete"),

    # shots
    path("shots/", shot_list, name="admin-shot-list"),
    path("shots/add/", shot_create, name="admin-shot-create"),
    path("shots/<int:pk>/edit/", shot_update, name="admin-shot-update"),
    path("shots/<int:pk>/delete/", shot_delete, name="admin-shot-delete"),
    
    path("logout", auth_views.LogoutView.as_view(), name='admin-logout')
]
