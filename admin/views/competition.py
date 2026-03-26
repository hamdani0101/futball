from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from admin.views.auth import admin_required 

from core.models import Competition

from admin.forms import CompetitionForm

@admin_required
def competition_list(request):
    page = request.GET.get("page", 1)
    query = (request.GET.get("q") or "").strip()
    kind = (request.GET.get("kind") or "all").strip().lower()
    per_page = 20
    competitions = Competition.objects.select_related("format").annotate(
        seasons_count=Count("season")
    )

    if query:
        competitions = competitions.filter(
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(country__icontains=query)
            | Q(format__name__icontains=query)
        )

    if kind == "league":
        competitions = competitions.filter(is_league=True)
    elif kind == "cup":
        competitions = competitions.filter(is_league=False)
    elif kind == "manual":
        competitions = competitions.filter(external_id__isnull=True)
    elif kind == "linked":
        competitions = competitions.filter(external_id__isnull=False)

    competitions = competitions.order_by("name")
    paginator = Paginator(competitions, per_page)
    page_obj = paginator.get_page(page)
    
    context = {
        "competitions": page_obj,
        "query": query,
        "kind": kind,
        "total_competitions": Competition.objects.count(),
        "league_competitions": Competition.objects.filter(is_league=True).count(),
        "cup_competitions": Competition.objects.filter(is_league=False).count(),
        "manual_competitions": Competition.objects.filter(external_id__isnull=True).count(),
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
        "admin/competition_form.html",
        {
            "form": form,
            "title": "Add Competition",
            "submit_label": "Save Competition",
            "subtitle": "Create a competition for manual data entry or external sync later.",
        },
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
        "admin/competition_form.html",
        {
            "form": form,
            "title": "Edit Competition",
            "submit_label": "Update Competition",
            "subtitle": "Refine competition metadata without depending on any external provider.",
            "competition": competition,
        },
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
