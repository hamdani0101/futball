from django.core.paginator import Paginator
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from admin.views.auth import admin_required 

from core.models import Competition

from admin.forms import CompetitionForm

@admin_required
def competition_list(request):
    page = request.GET.get("page", 1)
    per_page = 20
    competitions = Competition.objects.select_related("format").order_by("name")
    paginator = Paginator(competitions, per_page)
    page_obj = paginator.get_page(page)
    
    context = {
        "competitions": page_obj,
    }
    return render(request, "admin/competition_list.html", context)


@admin_required
def competition_create(request):
    form = CompetitionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Competition created successfully.")
        return redirect("admin-competition-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Add Competition", "submit_label": "Save Competition"},
    )


@admin_required
def competition_update(request, pk):
    competition = get_object_or_404(Competition, pk=pk)
    form = CompetitionForm(request.POST or None, request.FILES or None, instance=competition)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Competition updated successfully.")
        return redirect("admin-competition-list")
    return render(
        request,
        "admin/form.html",
        {"form": form, "title": "Edit Competition", "submit_label": "Update Competition"},
    )


@admin_required
def competition_delete(request, pk):
    competition = get_object_or_404(Competition, pk=pk)
    if request.method == "POST":
        competition.delete()
        messages.success(request, "Competition deleted successfully.")
        return redirect("admin-competition-list")
    return render(
        request,
        "admin/confirm_delete.html",
        {"object": competition, "title": "Delete Competition", "cancel_url": "admin-competition-list"},
    )
