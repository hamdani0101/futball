"""Views for fixture listings and match detail pages."""

from collections import defaultdict

from django.shortcuts import get_object_or_404, render
from core.models.match import Match
from core.models.match_team_stat import MatchTeamStats
from core.models.player_match import PlayerMatch
from core.models.shots import Shot


VALID_FIXTURE_TABS = {"all", "live", "postponed", "finished"}

ON_TARGET_OUTCOMES = {Shot.OUTCOME.GOAL, Shot.OUTCOME.SAVED}


def _team_stat(match, team):
    return next((stat for stat in match.team_stats.all() if stat.team_id == team.id), None)


def _format_minute(minute, second=0):
    if not minute and second:
        return "0'"
    return f"{minute}'"


def _period_meta(period):
    mapping = {
        1: {"label": "1ST HALF", "phase": "Regular Time"},
        2: {"label": "2ND HALF", "phase": "Regular Time"},
        3: {"label": "ET 1", "phase": "Extra Time"},
        4: {"label": "ET 2", "phase": "Extra Time"},
        5: {"label": "PEN", "phase": "Penalty Shootout"},
    }
    return mapping.get(period or 1, {"label": f"P{period or 1}", "phase": "Match Event"})


def _appearance_note(appearance):
    position = appearance.player.position or "Posisi belum diisi"
    minute_on = appearance.minute_on or 0
    minute_off = appearance.minute_off or 0

    if appearance.is_starter:
        if minute_off >= 120:
            status = "Starter • main sampai extra time selesai"
        elif minute_off >= 90:
            status = "Starter • main penuh"
        elif minute_off > 0:
            status = f"Starter • diganti menit {minute_off}'"
        else:
            status = "Starter"
    else:
        if minute_off >= 120:
            status = f"Masuk menit {minute_on}' • bertahan sampai akhir extra time"
        elif minute_off >= 90:
            status = f"Masuk menit {minute_on}' • menutup laga"
        elif minute_off > minute_on:
            status = f"Masuk menit {minute_on}' • keluar menit {minute_off}'"
        else:
            status = f"Masuk menit {minute_on}'"

    return {
        "player": appearance.player,
        "position_label": position,
        "status_label": status,
    }


def _percentage(part, total):
    if not total:
        return 0
    return round((part / total) * 100, 1)


def _stat_value(row, side):
    value = row.get(side, 0)
    if isinstance(value, float):
        return round(value, 2)
    return value


def _comparison_rows(home_stats, away_stats, home_shots, away_shots, home_lineup, away_lineup):
    rows = [
        {"label": "Goals", "home": (home_stats.goals if home_stats else 0) or 0, "away": (away_stats.goals if away_stats else 0) or 0},
        {"label": "xG", "home": (home_stats.xg if home_stats else 0) or 0, "away": (away_stats.xg if away_stats else 0) or 0},
        {"label": "Shots", "home": home_shots, "away": away_shots},
        {
            "label": "Shots on Target",
            "home": (home_stats.shots_on_target if home_stats else 0) or 0,
            "away": (away_stats.shots_on_target if away_stats else 0) or 0,
        },
        {"label": "Players Used", "home": home_lineup, "away": away_lineup},
    ]
    for row in rows:
        home_value = _stat_value(row, "home")
        away_value = _stat_value(row, "away")
        total = home_value + away_value
        if total:
            row["home_pct"] = round((home_value / total) * 100, 1)
            row["away_pct"] = round((away_value / total) * 100, 1)
        else:
            row["home_pct"] = 50
            row["away_pct"] = 50
    return rows


def _build_team_shot_summary(team, team_stats, team_shots, lineup_count):
    shot_count = team_shots.count() or ((team_stats.shots if team_stats else 0) or 0)
    on_target = team_shots.filter(outcome__in=ON_TARGET_OUTCOMES).count()
    if not on_target:
        on_target = (team_stats.shots_on_target if team_stats else 0) or 0
    xg_total = round(sum(shot.xg for shot in team_shots), 2) if team_shots else round((team_stats.xg if team_stats else 0) or 0, 2)
    goals = team_shots.filter(outcome=Shot.OUTCOME.GOAL).count()
    if not goals:
        goals = (team_stats.goals if team_stats else 0) or 0
    big_chances = team_shots.filter(is_big_chance=True).count()
    under_pressure = team_shots.filter(under_pressure=True).count()
    avg_distance = round(sum(shot.shot_distance for shot in team_shots) / len(team_shots), 1) if team_shots else 0
    open_play_shots = team_shots.filter(play_pattern=Shot.PLAY_PATTERN.OPEN_PLAY).count()
    set_piece_shots = team_shots.exclude(play_pattern=Shot.PLAY_PATTERN.OPEN_PLAY).exclude(play_pattern="").count()
    top_shooters = []
    shooter_map = defaultdict(lambda: {"shots": 0, "goals": 0, "xg": 0.0})
    for shot in team_shots:
        player_name = shot.player.name if shot.player else "Unknown"
        shooter_map[player_name]["shots"] += 1
        shooter_map[player_name]["goals"] += int(shot.outcome == Shot.OUTCOME.GOAL)
        shooter_map[player_name]["xg"] += shot.xg
    for player_name, stats in sorted(
        shooter_map.items(),
        key=lambda item: (item[1]["shots"], item[1]["xg"]),
        reverse=True,
    )[:3]:
        top_shooters.append(
            {
                "player": player_name,
                "shots": stats["shots"],
                "goals": stats["goals"],
                "xg": round(stats["xg"], 2),
            }
        )
    shot_log = [
        {
            "minute": _format_minute(shot.minute, shot.second),
            "player": shot.player.name if shot.player else "Unknown",
            "xg": round(shot.xg, 2),
            "outcome": shot.get_outcome_display(),
            "is_goal": shot.outcome == Shot.OUTCOME.GOAL,
        }
        for shot in team_shots.order_by("-xg", "minute", "second")[:5]
    ]

    return {
        "team": team,
        "goals": goals,
        "xg": xg_total,
        "shots": shot_count,
        "shots_on_target": on_target,
        "lineup_count": lineup_count,
        "big_chances": big_chances,
        "under_pressure": under_pressure,
        "avg_distance": avg_distance,
        "open_play_shots": open_play_shots,
        "set_piece_shots": set_piece_shots,
        "shot_accuracy": _percentage(on_target, shot_count),
        "conversion": _percentage(goals, shot_count),
        "top_shooters": top_shooters,
        "shot_log": shot_log,
        "best_chance": shot_log[0] if shot_log else None,
    }


def _build_match_timeline(home_team, away_team, shots, lineup_rows):
    events = []
    lineups_by_team = defaultdict(list)
    for appearance in lineup_rows:
        lineups_by_team[appearance.team_id].append(appearance)

    for shot in shots:
        if shot.outcome == Shot.OUTCOME.GOAL or shot.is_big_chance:
            period_meta = _period_meta(shot.period)
            if shot.period == 5 or shot.shot_type == Shot.SHOT_TYPE.PENALTY:
                badge = "PENALTY SCORED" if shot.outcome == Shot.OUTCOME.GOAL else "PENALTY MISSED"
            else:
                badge = "GOAL" if shot.outcome == Shot.OUTCOME.GOAL else "BIG CHANCE"

            if badge == "GOAL":
                title = f"{shot.player.name if shot.player else 'Unknown'} mencetak gol"
            elif badge.startswith("PENALTY"):
                title = f"{shot.player.name if shot.player else 'Unknown'} mengambil penalti"
            else:
                title = f"Peluang besar untuk {shot.player.name if shot.player else 'Unknown'}"

            events.append(
                {
                    "sort_key": (shot.period, shot.minute, shot.second, 0),
                    "minute": _format_minute(shot.minute, shot.second),
                    "team": shot.team,
                    "is_home": shot.team_id == home_team.id,
                    "badge": badge,
                    "period_label": period_meta["label"],
                    "phase": period_meta["phase"],
                    "title": title,
                    "detail": f"{shot.get_outcome_display()} dengan xG {round(shot.xg, 2)}",
                }
            )

    for appearance in lineup_rows:
        if not appearance.is_starter and appearance.minute_on > 0:
            period = 1
            if appearance.minute_on > 120:
                period = 5
            elif appearance.minute_on > 105:
                period = 4
            elif appearance.minute_on > 90:
                period = 3
            elif appearance.minute_on > 45:
                period = 2
            period_meta = _period_meta(period)
            player_off = next(
                (
                    row.player.name
                    for row in lineups_by_team.get(appearance.team_id, [])
                    if row.player_id != appearance.player_id and row.minute_off == appearance.minute_on
                ),
                None,
            )
            if player_off:
                title = f"{appearance.player.name} masuk menggantikan {player_off}"
            else:
                title = f"{appearance.player.name} masuk sebagai pengganti"
            events.append(
                {
                    "sort_key": (period, appearance.minute_on, 0, 1),
                    "minute": _format_minute(appearance.minute_on),
                    "team": appearance.team,
                    "is_home": appearance.team_id == home_team.id,
                    "badge": "SUB",
                    "period_label": period_meta["label"],
                    "phase": period_meta["phase"],
                    "title": title,
                    "detail": (
                        "Pergantian terjadi di extra time"
                        if period in [3, 4]
                        else "Pergantian pemain"
                    ),
                }
            )

    return sorted(events, key=lambda event: event["sort_key"])


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
    match = get_object_or_404(
        Match.objects.select_related("season__competition", "home_team", "away_team").prefetch_related("team_stats"),
        external_id=match_id,
    )
    home_stats = _team_stat(match, match.home_team)
    away_stats = _team_stat(match, match.away_team)

    lineup_rows = PlayerMatch.objects.filter(match=match).select_related("player", "team")
    home_starters = (
        lineup_rows.filter(team=match.home_team, is_starter=True)
        .order_by("minute_on", "player__name")
    )
    away_starters = (
        lineup_rows.filter(team=match.away_team, is_starter=True)
        .order_by("minute_on", "player__name")
    )
    home_bench = (
        lineup_rows.filter(team=match.home_team, is_starter=False)
        .order_by("minute_on", "player__name")
    )
    away_bench = (
        lineup_rows.filter(team=match.away_team, is_starter=False)
        .order_by("minute_on", "player__name")
    )
    home_starter_cards = [_appearance_note(item) for item in home_starters]
    away_starter_cards = [_appearance_note(item) for item in away_starters]
    home_bench_cards = [_appearance_note(item) for item in home_bench]
    away_bench_cards = [_appearance_note(item) for item in away_bench]

    shots = Shot.objects.filter(match=match).select_related("player", "assist_player", "team")
    home_team_shots = shots.filter(team=match.home_team).order_by("minute", "second", "id")
    away_team_shots = shots.filter(team=match.away_team).order_by("minute", "second", "id")
    home_goals = home_team_shots.filter(outcome=Shot.OUTCOME.GOAL, period__in=[1, 2])
    away_goals = away_team_shots.filter(outcome=Shot.OUTCOME.GOAL, period__in=[1, 2])

    home_shots = (home_stats.shots if home_stats else 0) or 0
    away_shots = (away_stats.shots if away_stats else 0) or 0
    home_sot = (home_stats.shots_on_target if home_stats else 0) or 0
    away_sot = (away_stats.shots_on_target if away_stats else 0) or 0
    home_goal_count = (home_stats.goals if home_stats else 0) or 0
    away_goal_count = (away_stats.goals if away_stats else 0) or 0
    home_xg = (home_stats.xg if home_stats else 0) or 0
    away_xg = (away_stats.xg if away_stats else 0) or 0

    home_lineup_count = len(home_starters) + len(home_bench)
    away_lineup_count = len(away_starters) + len(away_bench)
    comparison_rows = _comparison_rows(
        home_stats,
        away_stats,
        home_shots,
        away_shots,
        home_lineup_count,
        away_lineup_count,
    )
    more_stats = [
        {
            "label": "Shot Accuracy",
            "home": f"{_percentage(home_sot, home_shots)}%",
            "away": f"{_percentage(away_sot, away_shots)}%",
        },
        {
            "label": "Goal Conversion",
            "home": f"{_percentage(home_goal_count, home_shots)}%",
            "away": f"{_percentage(away_goal_count, away_shots)}%",
        },
        {
            "label": "xG per Shot",
            "home": round(home_xg / home_shots, 2) if home_shots else 0,
            "away": round(away_xg / away_shots, 2) if away_shots else 0,
        },
        {
            "label": "Players Used",
            "home": home_lineup_count,
            "away": away_lineup_count,
        },
    ]
    timeline_events = _build_match_timeline(match.home_team, match.away_team, shots, lineup_rows)
    home_summary = _build_team_shot_summary(
        match.home_team,
        home_stats,
        home_team_shots,
        home_lineup_count,
    )
    away_summary = _build_team_shot_summary(
        match.away_team,
        away_stats,
        away_team_shots,
        away_lineup_count,
    )
    headline_metrics = [
        {"label": "Total Shots", "value": home_summary["shots"] + away_summary["shots"]},
        {"label": "Total xG", "value": round(home_summary["xg"] + away_summary["xg"], 2)},
        {"label": "Big Chances", "value": home_summary["big_chances"] + away_summary["big_chances"]},
        {"label": "Timeline Events", "value": len(timeline_events)},
    ]
    match_info_rows = [
        {"label": "Match ID", "value": match.external_id},
        {"label": "Status", "value": match.status.replace("_", " ").title()},
        {"label": "Competition", "value": match.season.competition.name},
        {"label": "Season", "value": match.season.name},
        {"label": "Kickoff", "value": match.match_date.strftime("%d %b %Y • %H:%M")},
        {
            "label": "Lineups",
            "value": f"{home_lineup_count + away_lineup_count} players logged",
        },
    ]

    return render(
        request,
        "futball/match/match_detail.html",
        {
            "match": match,
            "home_stats": home_stats,
            "away_stats": away_stats,
            "home_starters": home_starters,
            "away_starters": away_starters,
            "home_bench": home_bench,
            "away_bench": away_bench,
            "home_starter_cards": home_starter_cards,
            "away_starter_cards": away_starter_cards,
            "home_bench_cards": home_bench_cards,
            "away_bench_cards": away_bench_cards,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "home_summary": home_summary,
            "away_summary": away_summary,
            "comparison_rows": comparison_rows,
            "more_stats": more_stats,
            "headline_metrics": headline_metrics,
            "match_info_rows": match_info_rows,
            "timeline_events": timeline_events,
        },
    )
