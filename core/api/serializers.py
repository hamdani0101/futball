"""Serializers for live match API responses."""

from rest_framework import serializers

from core.models.event import Event
from core.models.match import Match


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
    event_id = serializers.CharField(source="external_event_id")
    event_type = serializers.CharField(source="type")
    team_id = serializers.IntegerField(source="team.id")
    team_name = serializers.CharField(source="team.name")
    player_id = serializers.IntegerField(source="player.id", allow_null=True)
    player_name = serializers.CharField(source="player.name", allow_null=True)
    payload = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
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

    def get_payload(self, event):
        if event.type == Event.Type.SHOT and hasattr(event, "shot_detail"):
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
            return {
                "outcome": pass_event.outcome,
                "end_x": pass_event.end_x,
                "end_y": pass_event.end_y,
                "recipient_id": pass_event.recipient_id,
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


class LiveMatchSerializer(serializers.ModelSerializer):
    match_id = serializers.IntegerField(source="id")
    external_id = serializers.IntegerField(allow_null=True)
    home_team = serializers.CharField(source="home_team.name")
    away_team = serializers.CharField(source="away_team.name")
    score = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
    recent_events = serializers.SerializerMethodField()

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
        ]

    def get_score(self, match):
        stats_by_team = self._stats_by_team(match)
        home_stats = stats_by_team.get(match.home_team_id)
        away_stats = stats_by_team.get(match.away_team_id)

        return {
            "home": home_stats.score if home_stats else 0,
            "away": away_stats.score if away_stats else 0,
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
            "score": stats.score if stats else 0,
            "possession": stats.possession if stats else 0,
            "total_shots": stats.shots if stats else 0,
            "shots_on_target": stats.shots_on_target if stats else 0,
            "xg": round(stats.xg, 4) if stats else 0.0,
            "passes": stats.passes if stats else 0,
            "completed_passes": stats.completed_passes if stats else 0,
            "pass_accuracy": round(stats.pass_accuracy, 2) if stats else 0.0,
        }
