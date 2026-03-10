"""Views for fixture listings and match detail pages."""

from django.shortcuts import get_object_or_404, render
from futball.models.match import Match, MatchTeamStats


VALID_FIXTURE_TABS = {"all", "live", "postponed", "finished"}


def _build_match_item(match):
    """Build the fixture/result payload consumed by listing templates.

    The helper extracts goal totals from prefetched team statistics and exposes
    a ``has_score`` flag so templates know whether to render the scoreline.
    """
    home_goals = 0
    away_goals = 0
    for stat in match.team_stats.all():
        if stat.team_id == match.home_team_id:
            home_goals = stat.goals
        elif stat.team_id == match.away_team_id:
            away_goals = stat.goals

    return {
        "match": match,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "has_score": match.status in ["finished", "live"],
    }


def fixture_and_results(request):
    """Render the fixture and results page with status-based filtering.

    The page combines upcoming fixtures, recently finished matches, and any
    additional statuses such as live or postponed. A ``tab`` query parameter is
    normalized against ``VALID_FIXTURE_TABS`` to control which sections are
    visible without changing the underlying data preparation.
    """
    active_tab = request.GET.get("tab", "all").lower()
    if active_tab not in VALID_FIXTURE_TABS:
        active_tab = "all"

    upcoming_matches = (
        Match.objects.filter(status="scheduled")
        .select_related("season__competition", "home_team", "away_team")
        .prefetch_related("team_stats")
        .order_by("match_date")
    )
    recent_finished = (
        Match.objects.filter(status="finished")
        .select_related("season__competition", "home_team", "away_team")
        .prefetch_related("team_stats")
        .order_by("-match_date")[:10]
    )

    upcoming_items = [_build_match_item(match) for match in upcoming_matches]
    recent_results = [_build_match_item(match) for match in recent_finished]

    other_status_matches = (
        Match.objects.exclude(status__in=["scheduled", "finished"])
        .select_related("season__competition", "home_team", "away_team")
        .prefetch_related("team_stats")
        .order_by("-match_date")
    )

    grouped_statuses = {}
    for match in other_status_matches:
        grouped_statuses.setdefault(match.status, []).append(_build_match_item(match))

    preferred_order = ["live", "postponed", "paused", "cancelled"]
    ordered_statuses = [
        status for status in preferred_order if status in grouped_statuses
    ] + sorted(
        status for status in grouped_statuses if status not in preferred_order
    )

    status_sections = [
        {
            "status": status,
            "title": status.replace("_", " ").title(),
            "badge": status.upper(),
            "items": grouped_statuses[status],
            "empty_message": f"No {status.replace('_', ' ')} fixtures available.",
        }
        for status in ordered_statuses
    ]
    other_status_count = sum(len(section["items"]) for section in status_sections)

    upcoming_section = {
        "status": "scheduled",
        "title": "Fixture List",
        "badge": "UPCOMING",
        "items": upcoming_items,
        "empty_message": "No scheduled fixtures available.",
    }
    finished_section = {
        "status": "finished",
        "title": "Latest Results",
        "badge": "FINISHED",
        "items": recent_results,
        "empty_message": "No finished results available.",
    }

    all_sections = [upcoming_section, finished_section, *status_sections]

    if active_tab == "all":
        visible_sections = all_sections
    elif active_tab == "finished":
        visible_sections = [finished_section]
    else:
        target_status = active_tab
        matching_section = next(
            (section for section in status_sections if section["status"] == target_status),
            None,
        )
        if matching_section is None:
            matching_section = {
                "status": target_status,
                "title": target_status.replace("_", " ").title(),
                "badge": target_status.upper(),
                "items": [],
                "empty_message": f"No {target_status.replace('_', ' ')} fixtures available.",
            }
        visible_sections = [matching_section]

    filter_tabs = [
        {"key": "all", "label": "All"},
        {"key": "live", "label": "Live"},
        {"key": "postponed", "label": "Postponed"},
        {"key": "finished", "label": "Finished"},
    ]

    return render(
        request,
        "futball/match/fixture.html",
        {
            "upcoming_matches": upcoming_items,
            "recent_results": recent_results,
            "status_sections": status_sections,
            "other_status_count": other_status_count,
            "filter_tabs": filter_tabs,
            "active_tab": active_tab,
            "visible_sections": visible_sections,
        },
    )


def match_detail(request, match_id):
    """Render a single match detail page.

    The response includes team summary stats, separated starting and bench
    lineups, ordered goal events, and a few derived comparison metrics for the
    two sides.

    Args:
        request: The active Django ``HttpRequest``.
        match_id: Public match identifier used in the URL.

    Returns:
        HttpResponse: The rendered ``futball/match/match_detail.html`` page.
    """
    match = get_object_or_404(Match, match_id=match_id)
    home_stats = MatchTeamStats.objects.filter(match=match, team=match.home_team).first()
    away_stats = MatchTeamStats.objects.filter(match=match, team=match.away_team).first()
    return render(
        request,
        "futball/match/match_detail.html",
        {"match": match, "home_stats": home_stats, "away_stats": away_stats},
    )
