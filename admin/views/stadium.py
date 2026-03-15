from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from admin.views.auth import admin_required

from core.models import Stadium

from admin.forms import StadiumForm

@admin_required
def stadium_list(request):
    context = {
        "stadiums": Stadium.objects.order_by("name"),
    }
    return render(request, "admin/stadium_list.html", context)


@admin_required
def stadium_create(request):
    form = StadiumForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Stadium created successfully.")
        return redirect("stadium-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Add Stadium", "submit_label": "Save Stadium"},
    )


@admin_required
def stadium_update(request, pk):
    stadium = get_object_or_404(Stadium, pk=pk)
    form = StadiumForm(request.POST or None, instance=stadium)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Stadium updated successfully.")
        return redirect("stadium-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Edit Stadium", "submit_label": "Update Stadium"},
    )


@admin_required
def stadium_delete(request, pk):
    stadium = get_object_or_404(Stadium, pk=pk)
    if request.method == "POST":
        stadium.delete()
        messages.success(request, "Stadium deleted successfully.")
        return redirect("stadium-list")
    return render(
        request,
        "admin/confirm_delete.html",
        {"object": stadium, "title": "Delete Stadium", "cancel_url": "stadium-list"},
    )