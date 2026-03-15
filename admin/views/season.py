from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from admin.views.auth import admin_required

from core.models import Season

from admin.forms import SeasonForm


@admin_required
def season_list(request):
    context = {
        "seasons": Season.objects.select_related("competition").order_by("competition__name", "name"),
    }
    return render(request, "admin/season_list.html", context)


@admin_required
def season_create(request):
    form = SeasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Season created successfully.")
        return redirect("season-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Add Season", "submit_label": "Save Season"},
    )


@admin_required
def season_update(request, pk):
    season = get_object_or_404(Season, pk=pk)
    form = SeasonForm(request.POST or None, instance=season)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Season updated successfully.")
        return redirect("season-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Edit Season", "submit_label": "Update Season"},
    )


@admin_required
def season_delete(request, pk):
    season = get_object_or_404(Season, pk=pk)
    if request.method == "POST":
        season.delete()
        messages.success(request, "Season deleted successfully.")
        return redirect("season-list")
    return render(
        request,
        "admin/confirm_delete.html",
        {"object": season, "title": "Delete Season", "cancel_url": "season-list"},
    )