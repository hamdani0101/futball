from django.core.paginator import Paginator
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from admin.views.auth import admin_required

from core.models import Player

from admin.forms import PlayerForm

@admin_required
def player_list(request):
    page = request.GET.get("page", 1)
    per_page = 20
    players = Player.objects.select_related("team_now").order_by("name")
    paginator = Paginator(players, per_page)
    page_obj = paginator.get_page(page)
    
    context = {
        "players": page_obj,
    }
    return render(request, "admin/player_list.html", context)


@admin_required
def player_create(request):
    form = PlayerForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Player created successfully.")
        return redirect("admin-player-list")
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
        return redirect("admin-player-list")
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
        return redirect("admin-player-list")
    return render(
        request,
        "admin/confirm_delete.html",
        {"object": player, "title": "Delete Player", "cancel_url": "admin-player-list"},
    )
