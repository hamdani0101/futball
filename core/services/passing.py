"""Passing analytics services for players and teams."""

from django.db.models import Q

from core.models import Pass


PROGRESSIVE_DISTANCE_THRESHOLD = 10.0


def get_player_passing_stats(player, match=None, season=None):
    """Return aggregate passing statistics for a player."""
    scope = _filter_passes(Pass.objects.all(), match=match, season=season)
    queryset = scope.filter(player=player)
    return _build_passing_stats(queryset, scope)


def get_team_passing_stats(team, match=None, season=None):
    """Return aggregate passing statistics for a team."""
    scope = _filter_passes(Pass.objects.all(), match=match, season=season)
    queryset = scope.filter(team=team)
    return _build_passing_stats(queryset, scope)


def get_assist_chain_passes(match=None, season=None):
    """Return completed passes that belong to possessions ending with a shot assist."""
    scope = _filter_passes(Pass.objects.all(), match=match, season=season)
    possession_keys = list(
        scope.filter(Q(shot_assist=True) | Q(goal_assist=True))
        .values_list("match_id", "possession")
        .distinct()
    )
    if not possession_keys:
        return Pass.objects.none()

    filters = Q()
    for match_id, possession in possession_keys:
        filters |= Q(match_id=match_id, possession=possession)

    return scope.filter(filters).order_by("match_id", "possession", "event_index")


def _filter_passes(queryset, match=None, season=None):
    if match is not None:
        queryset = queryset.filter(match=match)
    if season is not None:
        queryset = queryset.filter(match__season=season)
    return queryset


def _build_passing_stats(queryset, scope):
    total_passes = queryset.count()
    completed_passes = queryset.filter(outcome=Pass.Outcome.COMPLETE).count()
    key_passes = queryset.filter(shot_assist=True).count()
    direct_goal_assists = queryset.filter(goal_assist=True).count()
    progressive_passes = _count_progressive_passes(queryset)
    assist_chain_passes = _count_assist_chain_passes(queryset, scope)
    assist_chain_possessions = _count_assist_chain_possessions(queryset, scope)

    completion_rate = round((completed_passes / total_passes) * 100, 2) if total_passes else 0.0

    return {
        "passes": total_passes,
        "completed_passes": completed_passes,
        "completion_rate": completion_rate,
        "key_passes": key_passes,
        "progressive_passes": progressive_passes,
        "goal_assists": direct_goal_assists,
        "assist_chain_passes": assist_chain_passes,
        "assist_chain_possessions": assist_chain_possessions,
    }


def _count_progressive_passes(queryset):
    count = 0
    for event in queryset.only("x", "y", "end_x", "end_y", "outcome").iterator():
        if event.outcome != Pass.Outcome.COMPLETE:
            continue
        if _is_progressive_pass(event.x, event.y, event.end_x, event.end_y):
            count += 1
    return count


def _count_assist_chain_passes(queryset, scope):
    possession_pairs = list(
        scope.filter(Q(shot_assist=True) | Q(goal_assist=True))
        .values_list("match_id", "possession")
        .distinct()
    )
    if not possession_pairs:
        return 0

    filters = Q()
    for match_id, possession in possession_pairs:
        filters |= Q(match_id=match_id, possession=possession)

    return queryset.filter(filters).count()


def _count_assist_chain_possessions(queryset, scope):
    possession_pairs = list(
        scope.filter(Q(shot_assist=True) | Q(goal_assist=True))
        .values_list("match_id", "possession")
        .distinct()
    )
    if not possession_pairs:
        return 0

    filters = Q()
    for match_id, possession in possession_pairs:
        filters |= Q(match_id=match_id, possession=possession)

    return (
        queryset.filter(filters)
        .values("match_id", "possession")
        .distinct()
        .count()
    )


def _is_progressive_pass(x, y, end_x, end_y):
    start_distance = _distance_to_goal(x, y)
    end_distance = _distance_to_goal(end_x, end_y)
    return (start_distance - end_distance) >= PROGRESSIVE_DISTANCE_THRESHOLD


def _distance_to_goal(x, y):
    goal_x = 120.0
    goal_y = 40.0
    return ((goal_x - x) ** 2 + (goal_y - y) ** 2) ** 0.5
