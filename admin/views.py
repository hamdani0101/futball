from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from futball.models.match import Match
from futball.models.player import Player
from futball.models.team import Team


@login_required
def dashboard(request):
    context = {
        "total_teams": Team.objects.count(),
        "total_players": Player.objects.count(),
        "total_matches": Match.objects.count(),
        "recent_matches": Match.objects.select_related("home_team", "away_team").order_by("-match_date")[:5],
    }
    return render(request, "admin/dashboard.html", context)

