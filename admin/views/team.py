from django.core.paginator import Paginator
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from admin.views.auth import admin_required

from core.models import Team

from admin.forms import TeamForm


@admin_required
def team_list(request):
    page = request.GET.get("page", 1)
    per_page = 20
    teams = Team.objects.order_by("-created_at")
    paginator = Paginator(teams, per_page)
    page_obj = paginator.get_page(page)
    
    context = {
        "teams": page_obj,
    }
    return render(request, "admin/team_list.html", context)


@admin_required
def team_create(request):
    form = TeamForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Team created successfully.")
        return redirect("admin-team-list")
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
        return redirect("admin-team-list")
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
        return redirect("admin-team-list")
    return render(
        request,
        "admin/confirm_delete.html",
        {"object": team, "title": "Delete Team", "cancel_url": "admin-team-list"},
    )