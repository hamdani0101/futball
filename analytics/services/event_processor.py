from core.models import MatchState, Shot


def process_event(event):
    state, _ = MatchState.objects.get_or_create(
        match=event.match,
        defaults={"status": event.match.status},
    )

    # ⏱ update time
    state.current_minute = event.minute
    state.current_second = event.second
    state.period = event.period
    state.status = event.match.status

    # ⚽ SHOT LOGIC
    if event.type == "shot":
        try:
            shot = event.shot_detail
        except Shot.DoesNotExist:
            shot = None

        if shot:
            if event.team_id == event.match.home_team_id:
                state.home_shots += 1
                state.home_xg += shot.xg
                if shot.is_goal:
                    state.home_score += 1
            else:
                state.away_shots += 1
                state.away_xg += shot.xg
                if shot.is_goal:
                    state.away_score += 1

    # 📌 last event
    state.last_event = event
    state.save()

    return state
