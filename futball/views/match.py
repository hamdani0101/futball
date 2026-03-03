from django.shortcuts import get_object_or_404, render
from futball.models.match import Match, MatchTeamStats


def fixture_and_results(request):
    matches = Match.objects.filter(status="scheduled").order_by("match_date")
    return render(request, "futball/match/fixture.html", {"matches": matches})


def match_detail(request, match_id):
    match = get_object_or_404(Match, match_id=match_id)
    home_stats = MatchTeamStats.objects.filter(match=match, team=match.home_team).first()
    away_stats = MatchTeamStats.objects.filter(match=match, team=match.away_team).first()
    return render(
        request,
        "futball/match/match_detail.html",
        {"match": match, "home_stats": home_stats, "away_stats": away_stats},
    )
