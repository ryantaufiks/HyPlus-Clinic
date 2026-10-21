from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy
from django.utils.text import format_lazy
from django_ratelimit.decorators import ratelimit

from kiosk import avatar_views, portal_views
from kiosk.portal_views import RoleAwareLoginView
from kiosk.views import healthz

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        ratelimit(key="ip", rate="10/m", method="POST", block=True)(RoleAwareLoginView.as_view()),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    # One-time link from an administrator to set a staff account's password.
    path(
        "accounts/setup/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/setup_password.html",
            success_url=format_lazy("{}?setup=done", reverse_lazy("login")),
        ),
        name="account-setup",
    ),
    # Patient portal
    path("portal/", portal_views.PortalHomeView.as_view(), name="portal-home"),
    path("portal/login/", portal_views.PortalLoginView.as_view(), name="portal-login"),
    path("portal/photo/", avatar_views.PortalPhotoView.as_view(), name="portal-photo"),
    path("portal/setup/<uidb64>/<token>/", portal_views.PortalSetupView.as_view(), name="portal-setup"),
    path(
        "portal/visits/<int:pk>/prescription/",
        portal_views.PortalPrescriptionView.as_view(),
        name="portal-prescription",
    ),
    path("", include("kiosk.urls")),
]
