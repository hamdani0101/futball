"""Serializers for live match API responses."""

import logging
import uuid

from rest_framework import serializers

from analytics.services.derived import derive_pass_metrics, derive_shot_metrics
from analytics.services.match_clock import current_clock
from core.models.event import Event
from core.models.shots import Shot
from core.models.save import Save
from core.models.match import Match

logger = logging.getLogger(__name__)

Pass = __import__("core.models.pass", fromlist=["Pass"]).Pass


class LiveTeamStatsSerializer(serializers.Serializer):
    team_id = serializers.IntegerField()
    team_name = serializers.CharField()
    score = serializers.IntegerField()
    possession = serializers.IntegerField()
    total_shots = serializers.IntegerField()
    shots_on_target = serializers.IntegerField()
    xg = serializers.FloatField()
    passes = serializers.IntegerField()
    completed_passes = serializers.IntegerField()
    pass_accuracy = serializers.FloatField()


class RecentEventSerializer(serializers.ModelSerializer):
    event_id = serializers.SerializerMethodField()
    event_type = serializers.CharField(source="type")
    team_id = serializers.SerializerMethodField()
    team_name = serializers.SerializerMethodField()
    player_id = serializers.SerializerMethodField()
    player_name = serializers.SerializerMethodField()
    payload = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "event_id",
            "event_type",
            "period",
            "minute",
            "second",
            "team_id",
            "team_name",
            "player_id",
            "player_name",
            "x",
            "y",
            "payload",
        ]

    def get_event_id(self, event):
        return event.external_event_id or str(event.pk)

    def get_team_id(self, event):
        return event.team_id

    def get_team_name(self, event):
        return event.team.name if event.team_id else ""

    def get_player_id(self, event):
        return event.player_id

    def get_player_name(self, event):
        return event.player.name if event.player_id else None

    def get_payload(self, event):
        if event.type in (Event.Type.SHOT, Event.Type.GOAL) and hasattr(event, "shot_detail"):
            shot = event.shot_detail
            return {
                "outcome": shot.outcome,
                "xg": round(shot.xg or 0, 4),
                "shot_type": shot.shot_type,
                "body_part": shot.body_part,
                "is_goal": shot.is_goal,
                "is_big_chance": shot.is_big_chance,
            }

        if event.type == Event.Type.PASS and hasattr(event, "pass_detail"):
            pass_event = event.pass_detail
            recipient = getattr(pass_event, "recipient", None)
            return {
                "outcome": pass_event.outcome,
                "end_x": pass_event.end_x,
                "end_y": pass_event.end_y,
                "recipient_id": pass_event.recipient_id,
                "recipient_name": recipient.name if recipient else None,
                "pass_type": pass_event.pass_type,
                "is_cross": pass_event.is_cross,
                "is_through_ball": pass_event.is_through_ball,
            }

        if event.type == Event.Type.SUBSTITUTION and hasattr(event, "substitution_detail"):
            substitution = event.substitution_detail
            return {
                "player_out_id": substitution.player_out_id,
                "player_in_id": substitution.player_in_id,
                "reason": substitution.reason,
            }

        return event.extra_data.get("payload", {}) if event.extra_data else {}


class EventCreateSerializer(serializers.ModelSerializer):
    payload = serializers.JSONField(required=False)

    class Meta:
        model = Event
        fields = [
            "type",
            "period",
            "minute",
            "second",
            "team",
            "player",
            "x",
            "y",
            "payload",
        ]

    def validate(self, attrs):
        match = self.context['match']
        team = attrs.get('team')
        player = attrs.get('player')
        x = attrs.get('x')
        y = attrs.get('y')
        minute = attrs.get('minute', 0)
        second = attrs.get('second', 0)
        event_type = attrs.get('type')
        payload = attrs.get('payload', {}) or {}
        payload = dict(payload)

        if team and team.id not in [match.home_team_id, match.away_team_id]:
            raise serializers.ValidationError("Team must participate in this match.")
        if player and team and player.team_now_id != team.id:
            raise serializers.ValidationError("Player must belong to the selected team.")
        if player and not team:
            raise serializers.ValidationError("Team is required when a player is set.")
        if x is not None and not (0 <= x <= 120):
            raise serializers.ValidationError("X coordinate must be between 0 and 120.")
        if y is not None and not (0 <= y <= 80):
            raise serializers.ValidationError("Y coordinate must be between 0 and 80.")
        # Server-authoritative clock: when the client omits minute/second the
        # server stamps the event with its own ticking clock. Explicit values
        # are still accepted so operators can correct historical entries.
        if 'minute' not in self.initial_data or 'second' not in self.initial_data:
            clock_minute, clock_second = current_clock(match)
            attrs.setdefault('minute', clock_minute)
            attrs.setdefault('second', clock_second)
            minute = attrs.get('minute', 0)
            second = attrs.get('second', 0)
        if 'period' not in self.initial_data:
            attrs.setdefault('period', match.period or 1)
        if minute is None or not (0 <= minute <= 130):
            raise serializers.ValidationError("Minute must be between 0 and 130.")
        if second is None or not (0 <= second <= 59):
            raise serializers.ValidationError("Second must be between 0 and 59.")

        if event_type == Event.Type.PASS:
            end_x = payload.get('end_x')
            end_y = payload.get('end_y')
            if end_x is not None and not (0 <= end_x <= 120):
                raise serializers.ValidationError("Pass end_x must be between 0 and 120.")
            if end_y is not None and not (0 <= end_y <= 80):
                raise serializers.ValidationError("Pass end_y must be between 0 and 80.")
            recipient_id = payload.get('recipient_id')
            if recipient_id:
                from core.models.player import Player
                try:
                    recipient = Player.objects.get(pk=recipient_id)
                except Player.DoesNotExist:
                    raise serializers.ValidationError("Recipient player does not exist.")
                if team and recipient.team_now_id != team.id:
                    raise serializers.ValidationError(
                        "Recipient must belong to the same team as the passer."
                    )
                if player and recipient.id == player.id:
                    raise serializers.ValidationError(
                        "Pass recipient cannot be the same as the passer."
                    )

        if event_type in (Event.Type.SHOT, Event.Type.GOAL):
            assist_id = payload.get('assist_player_id')
            if assist_id:
                from core.models.player import Player
                try:
                    assist_player = Player.objects.get(pk=assist_id)
                except Player.DoesNotExist:
                    raise serializers.ValidationError("Assist player does not exist.")
                if team and assist_player.team_now_id != team.id:
                    raise serializers.ValidationError(
                        "Assist player must belong to the shooting team."
                    )
            save_player_id = payload.get('save_player_id')
            if save_player_id:
                from core.models.player import Player
                try:
                    keeper = Player.objects.get(pk=save_player_id)
                except Player.DoesNotExist:
                    raise serializers.ValidationError("Save player does not exist.")
                if team and keeper.team_now_id == team.id:
                    raise serializers.ValidationError(
                        "Goalkeeper save must be made by the opposing team."
                    )
                if team and keeper.team_now_id not in [
                    match.home_team_id, match.away_team_id,
                ]:
                    raise serializers.ValidationError(
                        "Goalkeeper must participate in this match."
                    )

        if event_type == Event.Type.SAVE:
            if player and team and player.team_now_id != team.id:
                raise serializers.ValidationError(
                    "Save player must belong to the selected team."
                )

        if event_type == Event.Type.SUBSTITUTION:
            from core.models.player import Player
            out_id = payload.get('player_out_id')
            in_id = payload.get('player_in_id')
            if out_id and in_id and out_id == in_id:
                raise serializers.ValidationError(
                    "Substitution players must be different."
                )
            for pid in (out_id, in_id):
                if pid:
                    try:
                        sub_player = Player.objects.get(pk=pid)
                    except Player.DoesNotExist:
                        raise serializers.ValidationError(
                            "Substitution player does not exist."
                        )
                    if team and sub_player.team_now_id != team.id:
                        raise serializers.ValidationError(
                            "Substitution players must belong to the selected team."
                        )

        attrs['payload'] = payload
        return attrs

    def create(self, validated_data):
        from core.models.substitution import Substitution

        match = self.context['match']
        payload = dict(validated_data.pop('payload', {}) or {})
        event_type = validated_data['type']
        related_event_id = payload.get('related_event_id')
        related_event = None

        if related_event_id:
            try:
                related_event = Event.objects.get(pk=related_event_id, match=match)
            except Event.DoesNotExist:
                pass

        # Idempotency: every collected event gets a stable external id so a
        # Kafka retry never creates a duplicate statistic row.
        external_event_id = payload.get('external_event_id') or f"live-{uuid.uuid4().hex}"
        validated_data['external_event_id'] = external_event_id

        # Auto-advance possession/event ordering context.
        last = (
            Event.objects.filter(match=match)
            .order_by("-event_index", "-id")
            .values_list("event_index", "possession")
            .first()
        )
        validated_data.setdefault('event_index', (last[0] + 1) if last else 1)
        validated_data.setdefault('possession', (last[1] if last else 0) + 1)
        validated_data.setdefault('timestamp_ms', None)

        event = Event.objects.create(
            match=match,
            related_event=related_event,
            **validated_data
        )

        if event_type == Event.Type.SHOT or event_type == Event.Type.GOAL:
            outcome = payload.get('outcome', 'off_target')
            is_goal = outcome == 'goal' or event_type == Event.Type.GOAL
            if is_goal:
                outcome = 'goal'
                event.type = Event.Type.GOAL
                event.save(update_fields=['type', 'updated_at'])

            body_part = payload.get('body_part', 'right_foot')
            shot_x = validated_data.get('x', 0) or 0
            shot_y = validated_data.get('y', 0) or 0
            # SYSTEM CALCULATES: distance / angle / zone / xG. Never human-entered.
            derived = derive_shot_metrics(
                shot_x,
                shot_y,
                body_part=body_part,
                shot_type=payload.get('shot_type', 'open_play'),
                play_pattern=payload.get('play_pattern', ''),
                assist_type=payload.get('assist_type', ''),
                under_pressure=bool(payload.get('under_pressure', False)),
            )

            shot = Shot.objects.create(
                event=event,
                match=match,
                team=validated_data['team'],
                player=validated_data.get('player'),
                minute=validated_data['minute'],
                second=validated_data['second'],
                x=shot_x,
                y=shot_y,
                outcome=outcome,
                body_part=body_part,
                shot_type=payload.get('shot_type', 'open_play'),
                is_goal=is_goal,
                xg=derived['xg'],
                shot_distance=derived['distance'],
                shot_angle=derived['angle'],
                is_big_chance=derived['is_big_chance'],
                under_pressure=bool(payload.get('under_pressure', False)),
                period=validated_data.get('period', 1),
            )
            event.extra_data = {
                **(event.extra_data or {}),
                'derived': {
                    'distance': derived['distance'],
                    'angle': derived['angle'],
                    'zone': derived['zone'],
                    'xg': derived['xg'],
                },
            }
            event.save(update_fields=['extra_data', 'updated_at'])

            if outcome == 'saved' and payload.get('save_player_id'):
                from core.models.player import Player
                try:
                    save_player = Player.objects.get(pk=payload['save_player_id'])
                    save_event = Event.objects.create(
                        match=match,
                        period=validated_data.get('period', 1),
                        minute=validated_data['minute'],
                        second=validated_data['second'],
                        type=Event.Type.SAVE,
                        team_id=save_player.team_now_id,
                        player=save_player,
                        x=validated_data.get('x'),
                        y=validated_data.get('y'),
                        related_event=event,
                        external_event_id=f"live-{uuid.uuid4().hex}",
                        event_index=event.event_index + 1,
                        possession=event.possession,
                    )
                    Save.objects.create(
                        event=save_event,
                        match=match,
                        team_id=save_player.team_now_id,
                        player=save_player,
                        originating_shot=shot,
                        minute=validated_data['minute'],
                        second=validated_data['second'],
                    )
                except Player.DoesNotExist:
                    pass

            if payload.get('assist_player_id'):
                from core.models.player import Player
                try:
                    assist_player = Player.objects.get(pk=payload['assist_player_id'])
                    shot.assist_player = assist_player
                    shot.save(update_fields=['assist_player'])
                except Player.DoesNotExist:
                    pass

        elif event_type == Event.Type.PASS:
            start_x = validated_data.get('x', 0) or 0
            start_y = validated_data.get('y', 0) or 0
            end_x = payload.get('end_x', start_x)
            end_y = payload.get('end_y', start_y)
            # SYSTEM CALCULATES: length / direction / progressive / entries.
            derived = derive_pass_metrics(start_x, start_y, end_x, end_y)
            pass_row = Pass.objects.create(
                event=event,
                match=match,
                team=validated_data['team'],
                player=validated_data.get('player'),
                minute=validated_data['minute'],
                second=validated_data['second'],
                x=start_x,
                y=start_y,
                end_x=end_x,
                end_y=end_y,
                length=derived['length'],
                angle=derived['angle'],
                outcome=payload.get('outcome', 'complete'),
                recipient_id=payload.get('recipient_id'),
                is_through_ball=bool(payload.get('is_through_ball', False)),
                is_cross=bool(payload.get('is_cross', False)),
                period=validated_data.get('period', 1),
                possession=event.possession,
                event_index=event.event_index,
            )
            event.extra_data = {
                **(event.extra_data or {}),
                'derived': derived,
            }
            event.save(update_fields=['extra_data', 'updated_at'])

        elif event_type == Event.Type.SAVE:
            originating_shot = None
            if related_event and hasattr(related_event, 'shot_detail'):
                originating_shot = related_event.shot_detail
            Save.objects.create(
                event=event,
                match=match,
                team=validated_data['team'],
                player=validated_data.get('player'),
                originating_shot=originating_shot,
                minute=validated_data['minute'],
                second=validated_data['second'],
            )

        elif event_type == Event.Type.SUBSTITUTION:
            Substitution.objects.create(
                event=event,
                match=match,
                team=validated_data['team'],
                player_out_id=payload.get('player_out_id'),
                player_in_id=payload.get('player_in_id'),
                minute=validated_data['minute'],
                second=validated_data['second'],
                period=validated_data.get('period', 1),
                reason=payload.get('reason', ''),
            )

        # Server is authoritative for the match clock (not the browser).
        # updated_at is refreshed so the ticking clock has a fresh base.
        from django.utils import timezone
        Match.objects.filter(pk=match.pk).update(
            current_minute=validated_data.get('minute', 0),
            current_second=validated_data.get('second', 0),
            period=validated_data.get('period', 1),
            updated_at=timezone.now(),
        )

        # Incrementally refresh team aggregates from the event stream.
        try:
            from analytics.services.live_match_stats import update_live_match_stats
            update_live_match_stats(Event.objects.select_related(
                'team', 'match',
            ).prefetch_related('shot_detail', 'pass_detail').get(pk=event.pk))
        except Exception:
            logger.exception("Live stats refresh failed for event %s", event.pk)

        # Best-effort Kafka distribution: MySQL stays the source of truth.
        try:
            from django.conf import settings as dj_settings
            if getattr(dj_settings, "KAFKA_ENABLED", True):
                from analytics.services.kafka_producer import publish_match_event
                publish_match_event({
                'event_id': event.external_event_id,
                'event_type': event.type,
                'match_id': match.pk,
                'team_id': event.team_id,
                'player_id': event.player_id,
                'period': event.period,
                'minute': event.minute,
                'second': event.second,
                'payload': {
                    'location': {'x': event.x, 'y': event.y},
                    'outcome': payload.get('outcome'),
                    'derived': (event.extra_data or {}).get('derived', {}),
                },
            })
        except Exception:
            logger.warning(
                "Kafka publish failed for event %s; DB row retained", event.pk,
                exc_info=True,
            )

        return event

class LiveMatchSerializer(serializers.ModelSerializer):
    match_id = serializers.IntegerField(source="id")
    external_id = serializers.IntegerField(allow_null=True)
    home_team = serializers.CharField(source="home_team.name")
    away_team = serializers.CharField(source="away_team.name")
    score = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
    recent_events = serializers.SerializerMethodField()
    clock = serializers.SerializerMethodField()
    match_state = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            "match_id",
            "external_id",
            "status",
            "period",
            "current_minute",
            "current_second",
            "home_team",
            "away_team",
            "score",
            "stats",
            "recent_events",
            "clock",
            "match_state",
        ]

    def get_clock(self, match):
        from analytics.services.match_clock import clock_payload

        return clock_payload(match)

    def get_match_state(self, match):
        from analytics.services.match_clock import available_actions, display_state

        return {
            "state": display_state(match),
            "available_actions": available_actions(match),
        }

    def get_score(self, match):
        stats_by_team = self._stats_by_team(match)
        home_stats = stats_by_team.get(match.home_team_id)
        away_stats = stats_by_team.get(match.away_team_id)

        return {
            "home": home_stats.goals if home_stats else 0,
            "away": away_stats.goals if away_stats else 0,
        }

    def get_stats(self, match):
        return LiveTeamStatsSerializer(
            self._ordered_stats(match),
            many=True,
        ).data

    def get_recent_events(self, match):
        events = self.context.get("recent_events", [])
        return RecentEventSerializer(events, many=True).data

    def _ordered_stats(self, match):
        stats_by_team = self._stats_by_team(match)
        return [
            self._stat_payload(match.home_team, stats_by_team.get(match.home_team_id)),
            self._stat_payload(match.away_team, stats_by_team.get(match.away_team_id)),
        ]

    def _stats_by_team(self, match):
        if not hasattr(self, "_cached_stats_by_team"):
            self._cached_stats_by_team = {
                stats.team_id: stats
                for stats in getattr(match, "_prefetched_team_stats", [])
            }
        return self._cached_stats_by_team

    @staticmethod
    def _stat_payload(team, stats):
        return {
            "team_id": team.id,
            "team_name": team.name,
            "score": stats.goals if stats else 0,
            "possession": stats.possession if stats else 0,
            "total_shots": stats.shots if stats else 0,
            "shots_on_target": stats.shots_on_target if stats else 0,
            "xg": round(stats.xg, 4) if stats else 0.0,
            "passes": stats.passes if stats else 0,
            "completed_passes": stats.completed_passes if stats else 0,
            "pass_accuracy": round(stats.pass_accuracy, 2) if stats else 0.0,
        }
