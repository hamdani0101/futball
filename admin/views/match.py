from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from admin.views.auth import admin_required

from core.models import Match

from admin.forms import MatchForm

@admin_required
def match_list(request):
    context = {
        "matches": Match.objects.select_related("home_team", "away_team").order_by("-match_date"),
    }
    return render(request, "admin/match_list.html", context)


@admin_required
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


@admin_required
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


@admin_required
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
