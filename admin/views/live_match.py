from django.shortcuts import render, get_object_or_404, redirect
from core.models import Match, Event
from admin.views.auth import admin_required

@admin_required
def live_match_select(request):
    matches = Match.objects.order_by('-match_date')[:25]
    return render(request, "admin/live_match_select.html", {"matches": matches})

from core.models import Match, Event, Player

@admin_required
def live_match(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    events = (
        Event.objects.filter(match=match)
        .select_related("team", "player")
        .order_by("-period", "-minute", "-second", "-event_index", "-id")
    )
    players = Player.objects.filter(
        team_now__id__in=[match.home_team_id, match.away_team_id]
    ).order_by("team_now", "name")
    
    return render(request, "admin/live_match.html", {
        "match": match, 
        "events": events,
        "players": players
    })
