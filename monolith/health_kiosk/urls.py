from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django_ratelimit.decorators import ratelimit

from kiosk.views import healthz

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        ratelimit(key="ip", rate="10/m", method="POST", block=True)(
            auth_views.LoginView.as_view(redirect_authenticated_user=True)
        ),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("kiosk.urls")),
]
