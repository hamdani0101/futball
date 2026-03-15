from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from admin.views.auth import admin_required

from core.models import Player

from admin.forms import PlayerForm

@admin_required
def player_list(request):
    context = {
        "players": Player.objects.select_related("team_now").order_by("name"),
    }
    return render(request, "admin/player_list.html", context)


@admin_required
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


@admin_required
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


@admin_required
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