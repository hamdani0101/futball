from django.shortcuts import render
from admin.views.auth import admin_required

from core.models import Match, Player, Team

@admin_required
def dashboard(request):
    context = {
        "total_teams": Team.objects.count(),
        "total_players": Player.objects.count(),
        "total_matches": Match.objects.count(),
    }
    return render(request, "admin/dashboard.html", context)