"""Staff accounts, managed by administrators from the app.

Administrators never choose a staff member's password: creating an account
(or resetting a password) produces a one-time setup link that the staff
member opens to set their own password.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views import View
from django.views.generic import TemplateView

from .forms import StaffAccountForm
from .models import AuditEvent, StaffProfile
from .roles import ROLE_LABELS, AdminRequiredMixin, apply_role, role_of

User = get_user_model()


def setup_link(request, user):
    """One-time link to set a password; it stops working once a password is set."""
    path = reverse(
        "account-setup",
        kwargs={"uidb64": urlsafe_base64_encode(force_bytes(user.pk)), "token": default_token_generator.make_token(user)},
    )
    return settings.PUBLIC_BASE_URL + path if settings.PUBLIC_BASE_URL else request.build_absolute_uri(path)


def _link_page(request, user, created):
    return render(
        request,
        "kiosk/staff_link.html",
        {
            "member": user,
            "role": ROLE_LABELS[role_of(user)],
            "link": setup_link(request, user),
            "created": created,
            "valid_days": settings.PASSWORD_RESET_TIMEOUT // 86400,
        },
    )


def _initial(member):
    profile = StaffProfile.objects.filter(user=member).first()
    return {"role": role_of(member), "room": profile.room if profile else ""}


def _save_room(user, room):
    StaffProfile.objects.update_or_create(user=user, defaults={"room": room.strip()})


class StaffListView(AdminRequiredMixin, TemplateView):
    template_name = "kiosk/staff_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        users = User.objects.prefetch_related("groups").select_related("profile").order_by("-is_active", "first_name", "username")
        context["members"] = [
            {
                "user": u,
                "role": ROLE_LABELS[role_of(u)],
                "room": getattr(getattr(u, "profile", None), "room", ""),
                "on_duty": getattr(getattr(u, "profile", None), "on_duty", True),
                "activated": u.has_usable_password(),
            }
            for u in users
        ]
        return context


class StaffCreateView(AdminRequiredMixin, View):
    template_name = "kiosk/staff_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": StaffAccountForm(initial={"role": "nurse"}), "creating": True})

    def post(self, request):
        form = StaffAccountForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "creating": True})
        with transaction.atomic():
            user = form.save(commit=False)
            user.set_unusable_password()
            user.save()
            apply_role(user, form.cleaned_data["role"])
            _save_room(user, form.cleaned_data["room"])
            AuditEvent.record(request.user, "staff.created", username=user.username, role=form.cleaned_data["role"])
        return _link_page(request, user, created=True)


class StaffEditView(AdminRequiredMixin, View):
    template_name = "kiosk/staff_form.html"

    def _context(self, member, form):
        return {"form": form, "member": member, "is_self": member == self.request.user}

    def get(self, request, pk):
        member = get_object_or_404(User, pk=pk)
        form = StaffAccountForm(instance=member, initial=_initial(member), editing_self=member == request.user)
        return render(request, self.template_name, self._context(member, form))

    def post(self, request, pk):
        member = get_object_or_404(User, pk=pk)
        is_self = member == request.user
        action = request.POST.get("action")

        if action in ("deactivate", "activate"):
            if is_self:
                messages.error(request, "You cannot deactivate your own account.")
            else:
                member.is_active = action == "activate"
                member.save(update_fields=["is_active"])
                AuditEvent.record(request.user, f"staff.{action}d", username=member.username)
                messages.success(request, f"{member.get_full_name() or member.username} {'activated' if member.is_active else 'deactivated'}.")
            return redirect("kiosk:staff-list")

        if action == "setup-link":
            AuditEvent.record(request.user, "staff.setup_link", username=member.username)
            return _link_page(request, member, created=False)

        form = StaffAccountForm(request.POST, instance=member, initial=_initial(member), editing_self=is_self)
        if not form.is_valid():
            return render(request, self.template_name, self._context(member, form))
        with transaction.atomic():
            form.save()
            if not is_self:
                apply_role(member, form.cleaned_data["role"])
            _save_room(member, form.cleaned_data["room"])
            AuditEvent.record(request.user, "staff.updated", username=member.username, role=role_of(member))
        messages.success(request, "Account saved.")
        return redirect("kiosk:staff-list")
