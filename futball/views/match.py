from django.shortcuts import get_object_or_404, render
from futball.models.match import Match, MatchTeamStats


def fixture_and_results(request):
    upcoming_matches = (
        Match.objects.filter(status="scheduled")
        .select_related("season__competition", "home_team", "away_team")
        .order_by("match_date")
    )
    recent_finished = (
        Match.objects.filter(status="finished")
        .select_related("season__competition", "home_team", "away_team")
        .prefetch_related("team_stats")
        .order_by("-match_date")[:10]
    )

    recent_results = []
    for match in recent_finished:
        home_goals = 0
        away_goals = 0
        for stat in match.team_stats.all():
            if stat.team_id == match.home_team_id:
                home_goals = stat.goals
            elif stat.team_id == match.away_team_id:
                away_goals = stat.goals
        recent_results.append(
            {"match": match, "home_goals": home_goals, "away_goals": away_goals}
        )

    return render(
        request,
        "futball/match/fixture.html",
        {"upcoming_matches": upcoming_matches, "recent_results": recent_results},
    )


def match_detail(request, match_id):
    match = get_object_or_404(Match, match_id=match_id)
    home_stats = MatchTeamStats.objects.filter(match=match, team=match.home_team).first()
    away_stats = MatchTeamStats.objects.filter(match=match, team=match.away_team).first()
    return render(
        request,
        "futball/match/match_detail.html",
        {"match": match, "home_stats": home_stats, "away_stats": away_stats},
    )
