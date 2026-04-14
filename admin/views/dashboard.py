from datetime import timedelta

from django.db.models import Count, F, Q
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from admin.views.auth import admin_required

from core.models import Match, MatchTeamStats, Player, Shot, Team


def _trend_percentage(current_value, previous_value):
    if previous_value == 0:
        return 100 if current_value > 0 else 0
    return round(((current_value - previous_value) / previous_value) * 100)


@admin_required
def dashboard(request):
    now = timezone.now()
    current_window_start = now - timedelta(days=30)
    previous_window_start = current_window_start - timedelta(days=30)

    total_teams = Team.objects.count()
    total_players = Player.objects.count()
    total_matches = Match.objects.count()
    total_match_stats = MatchTeamStats.objects.count()
    total_shots = Shot.objects.count()

    team_trend = _trend_percentage(
        Team.objects.filter(created_at__gte=current_window_start).count(),
        Team.objects.filter(
            created_at__gte=previous_window_start,
            created_at__lt=current_window_start,
        ).count(),
    )
    player_trend = _trend_percentage(
        Player.objects.filter(created_at__gte=current_window_start).count(),
        Player.objects.filter(
            created_at__gte=previous_window_start,
            created_at__lt=current_window_start,
        ).count(),
    )
    match_trend = _trend_percentage(
        Match.objects.filter(created_at__gte=current_window_start).count(),
        Match.objects.filter(
            created_at__gte=previous_window_start,
            created_at__lt=current_window_start,
        ).count(),
    )
    shot_trend = _trend_percentage(
        Shot.objects.filter(created_at__gte=current_window_start).count(),
        Shot.objects.filter(
            created_at__gte=previous_window_start,
            created_at__lt=current_window_start,
        ).count(),
    )

    monthly_matches = (
        Match.objects.filter(match_date__gte=now - timedelta(days=180))
        .annotate(month=TruncMonth("match_date"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )
    matches_over_time_labels = [item["month"].strftime("%b %Y") for item in monthly_matches if item["month"]]
    matches_over_time_values = [item["total"] for item in monthly_matches]

    recent_match_bars = list(
        Match.objects.select_related("home_team", "away_team")
        .annotate(
            home_goals=Count("shots", filter=Q(shots__team_id=F("home_team_id"), shots__is_goal=True)),
            away_goals=Count("shots", filter=Q(shots__team_id=F("away_team_id"), shots__is_goal=True)),
            total_shots=Count("shots"),
            total_goals=Count("shots", filter=Q(shots__is_goal=True)),
        )
        .order_by("-match_date")[:6]
    )

    recent_matches = list(
        Match.objects.select_related("home_team", "away_team", "season__competition")
        .annotate(
            home_goals=Count("shots", filter=Q(shots__team_id=F("home_team_id"), shots__is_goal=True)),
            away_goals=Count("shots", filter=Q(shots__team_id=F("away_team_id"), shots__is_goal=True)),
            total_shots=Count("shots"),
        )
        .order_by("-match_date")[:8]
    )

    context = {
        "total_teams": total_teams,
        "total_players": total_players,
        "total_matches": total_matches,
        "total_match_stats": total_match_stats,
        "total_shots": total_shots,
        "team_trend": team_trend,
        "player_trend": player_trend,
        "match_trend": match_trend,
        "shot_trend": shot_trend,
        "matches_over_time_labels": matches_over_time_labels,
        "matches_over_time_values": matches_over_time_values,
        "match_bar_labels": [f"{match.home_team.name[:3].upper()} vs {match.away_team.name[:3].upper()}" for match in reversed(recent_match_bars)],
        "match_bar_goals": [match.total_goals for match in reversed(recent_match_bars)],
        "match_bar_shots": [match.total_shots for match in reversed(recent_match_bars)],
        "recent_matches": recent_matches,
    }
    return render(request, "admin/dashboard.html", context)
