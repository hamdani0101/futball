"""Player-related views for the futball app."""

from django.shortcuts import get_object_or_404, render

from core.models.player import Player
from core.models.player_match import PlayerMatch
from analytics.services.player_metrics import (
    get_player_match_stats,
    get_player_profile_stats,
)


def player_list(request):
    """Render a simple player index page."""
    players = (
        Player.objects.select_related("team_now")
        .order_by("name")
    )
    return render(
        request,
        "futball/player/player_list.html",
        {"players": players},
    )


def player_profile(request, player_id):
    """Render a player profile page with summary stats."""
    player = get_object_or_404(
        Player.objects.select_related("team_now"),
        pk=player_id,
    )
    profile_stats = get_player_profile_stats(player)
    recent_matches = get_player_match_stats(player, limit=5)

    return render(
        request,
        "futball/player/player_profile.html",
        {
            "player": player,
            "profile_stats": profile_stats,
            "recent_matches": recent_matches,
        },
    )


def player_stats(request, player_id):
    """Render detailed player match-by-match statistics."""
    player = get_object_or_404(
        Player.objects.select_related("team_now"),
        pk=player_id,
    )
    profile_stats = get_player_profile_stats(player)
    total_matches = PlayerMatch.objects.filter(player=player).count()
    match_stats = get_player_match_stats(player, limit=total_matches)

    return render(
        request,
        "futball/player/player_stats.html",
        {
            "player": player,
            "profile_stats": profile_stats,
            "match_stats": match_stats,
        },
    )
