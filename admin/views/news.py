from django.core.paginator import Paginator
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from admin.views.auth import admin_required

from core.models.news import News


@admin_required
def news_list(request):
    page = request.GET.get("page", 1)
    per_page = 20
    news = News.objects.order_by("-created_at").all()
    paginator = Paginator(news, per_page)
    page_obj = paginator.get_page(page)
    
    context = {
        "news": page_obj,
    }
    return render(request, "admin/news_list.html", context)