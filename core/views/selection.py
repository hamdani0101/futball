"""Shared helpers for resolving competition and season filters from requests."""

from django.core import serializers

from core.models.competition import Competition
from core.models.season import Season


def get_competition_season_selection(request):
    """Resolve shared competition and season filters for stats pages."""
    competitions = Competition.objects.order_by("name")
    seasons_all = Season.objects.order_by("-name")

    competition_id = request.GET.get("competition")
    season_id = request.GET.get("season")

    selected_competition = (
        competitions.filter(id=competition_id).first()
        if competition_id
        else competitions.first()
    )
    seasons = (
        seasons_all.filter(competition=selected_competition)
        if selected_competition
        else Season.objects.none()
    )
    selected_season = (
        seasons.filter(id=season_id).first()
        if season_id
        else seasons.first()
    )

    return {
        "competitions": competitions,
        "seasons_all": seasons_all,
        "seasons": seasons,
        "selected_competition": selected_competition,
        "selected_season": selected_season,
        "season_json_data": serializers.serialize("json", seasons_all),
    }
