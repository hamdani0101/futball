from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from admin.forms import ShotForm
from admin.views.auth import admin_required
from core.models import Shot


@admin_required
def shot_list(request):
    page = request.GET.get("page", 1)
    per_page = 20
    shots = (
        Shot.objects.select_related(
            "match__home_team",
            "match__away_team",
            "team",
            "player",
        )
        .order_by("-match__match_date", "minute", "second")
    )
    paginator = Paginator(shots, per_page)
    page_obj = paginator.get_page(page)
    return render(request, "admin/shot_list.html", {"shots": page_obj})


@admin_required
def shot_create(request):
    form = ShotForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Shot created successfully.")
        return redirect("admin-shot-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Add Shot", "submit_label": "Save Shot"},
    )


@admin_required
def shot_update(request, pk):
    shot = get_object_or_404(Shot, pk=pk)
    form = ShotForm(request.POST or None, instance=shot)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Shot updated successfully.")
        return redirect("admin-shot-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Edit Shot", "submit_label": "Update Shot"},
    )


@admin_required
def shot_delete(request, pk):
    shot = get_object_or_404(Shot, pk=pk)
    if request.method == "POST":
        shot.delete()
        messages.success(request, "Shot deleted successfully.")
        return redirect("admin-shot-list")
    return render(
        request,
        "admin/confirm_delete.html",
        {
            "object": shot,
            "title": "Delete Shot",
            "cancel_url": "admin-shot-list",
        },
    )
