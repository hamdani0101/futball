from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import include, path
from admin.views.auth import RoleAwareLoginView, register_view

urlpatterns = [
    path("login/", RoleAwareLoginView.as_view(), name="login"),
    path("register/", register_view, name="register"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", include("admin.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATIC_ROOT
    )
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
