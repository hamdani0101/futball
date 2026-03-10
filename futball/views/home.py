"""Views used to render the futball landing page.

The home page combines summary counts, recent news, live-or-recent match
trackers, and upcoming fixtures into a single template context.
"""

from django.shortcuts import render
from django.utils import timezone
from django.http import HttpResponse
from futball.models.competition import Competition
from futball.models.match import Match, MatchTeamStats
from futball.models.news import News
from futball.models.season import Season
from futball.models.team import Team


def _status_badge(status):
    """Map an internal match status to the compact badge shown in the UI."""
    return {
        "finished": "FT",
        "scheduled": "SCH",
        "postponed": "PST",
    }.get(status, status.upper())


def _build_match_cards(matches):
    """Convert matches into card dictionaries expected by the home template.

    Each card includes the match object, the cached goal totals for both teams,
    and a short status badge so templates do not need to repeat lookup logic.
    """
    matches = list(matches)
    if not matches:
        return []

    stats_qs = MatchTeamStats.objects.filter(match__in=matches).only("match_id", "team_id", "goals")
    stats_map = {}
    for stat in stats_qs:
        stats_map[(stat.match_id, stat.team_id)] = stat.goals

    cards = []
    for match in matches:
        cards.append(
            {
                "match": match,
                "home_goals": stats_map.get((match.id, match.home_team_id)),
                "away_goals": stats_map.get((match.id, match.away_team_id)),
                "status_badge": _status_badge(match.status),
            }
        )
    return cards


def home_view(request):
    """Render the futball home page.

    The view assembles:
    - headline news items
    - a match tracker for today's fixtures, or recent results as a fallback
    - a spotlight match that prefers the next scheduled fixture
    - recent results and upcoming fixtures
    - aggregate counts used by home page summary panels

    Args:
        request: The active Django ``HttpRequest``.

    Returns:
        HttpResponse: The rendered ``futball/home.html`` response.
    """
    latest_news = News.objects.all().order_by("-created_at")[:4]
    today = timezone.localdate()

    today_matches_qs = (
        Match.objects.filter(match_date__date=today)
        .select_related("season__competition", "home_team", "away_team")
        .order_by("match_date")
    )
    recent_results_qs = (
        Match.objects.filter(status="finished")
        .select_related("season__competition", "home_team", "away_team")
        .order_by("-match_date")[:6]
    )
    upcoming_qs = (
        Match.objects.filter(status="scheduled", match_date__date__gte=today)
        .select_related("season__competition", "home_team", "away_team")
        .order_by("match_date")
    )

    upcoming_first = upcoming_qs.first()
    recent_first = recent_results_qs.first()
    spotlight_match = upcoming_first or recent_first
    spotlight_mode = "upcoming" if upcoming_first else "result"

    tracker_matches = list(today_matches_qs[:6])
    tracker_title = "Today Match Tracker"
    tracker_subtitle = today.strftime("%a, %d %b %Y")

    if not tracker_matches and recent_first:
        tracker_matches = list(recent_results_qs)
        tracker_title = "Latest Results Tracker"
        tracker_subtitle = recent_first.match_date.strftime("%a, %d %b %Y")

    tracker_cards = _build_match_cards(tracker_matches)
    spotlight_card = _build_match_cards([spotlight_match])[0] if spotlight_match else None

    context = {
        "total_competitions": Competition.objects.count(),
        "total_seasons": Season.objects.count(),
        "total_teams": Team.objects.count(),
        "upcoming_matches": Match.objects.filter(status="scheduled").count(),
        "today_matches": tracker_cards,
        "tracker_title": tracker_title,
        "tracker_subtitle": tracker_subtitle,
        "recent_results": _build_match_cards(recent_results_qs),
        "next_fixtures": _build_match_cards(upcoming_qs[:6]),
        "spotlight": spotlight_card,
        "spotlight_mode": spotlight_mode,
        "news": latest_news,
    }
    return render(request, "futball/home.html", context)
