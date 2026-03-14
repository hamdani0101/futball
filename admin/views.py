from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from futball.models import Match, Player, Team

from .forms import MatchForm, PlayerForm, TeamForm


@login_required
def dashboard(request):
    context = {
        "total_teams": Team.objects.count(),
        "total_players": Player.objects.count(),
        "total_matches": Match.objects.count(),
    }
    return render(request, "admin/dashboard.html", context)


@login_required
def team_list(request):
    context = {
        "teams": Team.objects.order_by("name"),
    }
    return render(request, "admin/team_list.html", context)


@login_required
def team_create(request):
    form = TeamForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Team created successfully.")
        return redirect("team-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Add Team", "submit_label": "Save Team"},
    )


@login_required
def team_update(request, pk):
    team = get_object_or_404(Team, pk=pk)
    form = TeamForm(request.POST or None, request.FILES or None, instance=team)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Team updated successfully.")
        return redirect("team-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Edit Team", "submit_label": "Update Team"},
    )


@login_required
def team_delete(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if request.method == "POST":
        team.delete()
        messages.success(request, "Team deleted successfully.")
        return redirect("team-list")
    return render(
        request,
        "admin/confirm_delete.html",
        {"object": team, "title": "Delete Team", "cancel_url": "team-list"},
    )


@login_required
def player_list(request):
    context = {
        "players": Player.objects.select_related("team_now").order_by("name"),
    }
    return render(request, "admin/player_list.html", context)


@login_required
def player_create(request):
    form = PlayerForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Player created successfully.")
        return redirect("player-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Add Player", "submit_label": "Save Player"},
    )


@login_required
def player_update(request, pk):
    player = get_object_or_404(Player, pk=pk)
    form = PlayerForm(request.POST or None, request.FILES or None, instance=player)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Player updated successfully.")
        return redirect("player-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Edit Player", "submit_label": "Update Player"},
    )


@login_required
def player_delete(request, pk):
    player = get_object_or_404(Player, pk=pk)
    if request.method == "POST":
        player.delete()
        messages.success(request, "Player deleted successfully.")
        return redirect("player-list")
    return render(
        request,
        "admin/confirm_delete.html",
        {"object": player, "title": "Delete Player", "cancel_url": "player-list"},
    )


@login_required
def match_list(request):
    context = {
        "matches": Match.objects.select_related("home_team", "away_team").order_by("-match_date"),
    }
    return render(request, "admin/match_list.html", context)


@login_required
def match_create(request):
    form = MatchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Match created successfully.")
        return redirect("match-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Add Match", "submit_label": "Save Match"},
    )


@login_required
def match_update(request, pk):
    match = get_object_or_404(Match, pk=pk)
    form = MatchForm(request.POST or None, instance=match)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Match updated successfully.")
        return redirect("match-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Edit Match", "submit_label": "Update Match"},
    )


@login_required
def match_delete(request, pk):
    match = get_object_or_404(Match, pk=pk)
    if request.method == "POST":
        match.delete()
        messages.success(request, "Match deleted successfully.")
        return redirect("match-list")
    return render(
        request,
        "admin/confirm_delete.html",
        {"object": match, "title": "Delete Match", "cancel_url": "match-list"},
    )
