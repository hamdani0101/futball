from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse


class RoleAwareLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        next_url = self.get_redirect_url()
        if next_url:
            return next_url
        if self.request.user.is_staff:
            return reverse("dashboard")
        return reverse("home")


def register_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect("dashboard")
        return redirect("home")

    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Registrasi berhasil. Selamat datang di Futball.")
        return redirect("home")

    return render(request, "registration/register.html", {"form": form})


def admin_required(view_func):
    protected_view = login_required(view_func)

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return protected_view(request, *args, **kwargs)
        if not request.user.is_staff:
            messages.error(request, "Akun ini tidak punya akses ke halaman data entry Futball.")
            return redirect("home")
        return protected_view(request, *args, **kwargs)

    return wrapped_view