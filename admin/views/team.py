from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from admin.views.auth import admin_required

from core.models import Team

from admin.forms import TeamForm


@admin_required
def team_list(request):
    context = {
        "teams": Team.objects.order_by("name"),
    }
    return render(request, "admin/team_list.html", context)


@admin_required
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


@admin_required
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


@admin_required
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