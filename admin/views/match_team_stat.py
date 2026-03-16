from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from admin.forms import MatchTeamStatsForm
from admin.views.auth import admin_required
from core.models import MatchTeamStats


@admin_required
def match_team_stat_list(request):
    page = request.GET.get("page", 1)
    per_page = 20
    stats = (
        MatchTeamStats.objects.select_related(
            "match__home_team",
            "match__away_team",
            "team",
        )
        .order_by("-match__match_date", "team__name")
    )
    paginator = Paginator(stats, per_page)
    page_obj = paginator.get_page(page)
    return render(request, "admin/match_team_stat_list.html", {"stats": page_obj})


@admin_required
def match_team_stat_create(request):
    form = MatchTeamStatsForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Match stats created successfully.")
        return redirect("admin-match-stat-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Add Match Stats", "submit_label": "Save Stats"},
    )


@admin_required
def match_team_stat_update(request, pk):
    stat = get_object_or_404(MatchTeamStats, pk=pk)
    form = MatchTeamStatsForm(request.POST or None, instance=stat)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Match stats updated successfully.")
        return redirect("admin-match-stat-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Edit Match Stats", "submit_label": "Update Stats"},
    )


@admin_required
def match_team_stat_delete(request, pk):
    stat = get_object_or_404(MatchTeamStats, pk=pk)
    if request.method == "POST":
        stat.delete()
        messages.success(request, "Match stats deleted successfully.")
        return redirect("admin-match-stat-list")
    return render(
        request,
        "admin/confirm_delete.html",
        {
            "object": stat,
            "title": "Delete Match Stats",
            "cancel_url": "admin-match-stat-list",
        },
    )
