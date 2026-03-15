"""Team xG aggregation for a single match."""

from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce

from core.models.match import Match
from core.models.team import Team


def calculate_team_xg_per_match(match_id):
    """Return team xG, shot count, and goals for the given match identifier."""
    match = Match.objects.get(match_id=match_id)

    team_ids = [match.home_team_id, match.away_team_id]

    teams = (
        Team.objects.filter(id__in=team_ids)
        .annotate(
            xg=Coalesce(
                Sum("shots__xg", filter=Q(shots__match=match)),
                Value(0.0),
            ),
            shots=Count("shots", filter=Q(shots__match=match)),
            goals=Count("shots", filter=Q(shots__match=match, shots__is_goal=True)),
        )
        .values("id", "name", "xg", "shots", "goals")
    )

    team_map = {team["id"]: team for team in teams}

    results = []
    for team_id in team_ids:
        team = team_map[team_id]
        results.append(
            {
                "team_name": team["name"],
                "xg": team["xg"],
                "shots": team["shots"],
                "goals": team["goals"],
            }
        )

    return results
