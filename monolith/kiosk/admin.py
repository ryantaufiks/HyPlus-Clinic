from django import forms
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .models import Measurement, Patient, QueueTicket, SiteConfiguration

admin.site.site_header = "AIVIN administration"
admin.site.site_title = "AIVIN admin"
admin.site.index_title = "AIVIN — AI-Vital Intake"


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["name", "symptoms", "created_at"]
    search_fields = ["name", "symptoms"]
    list_filter = ["created_at"]
    readonly_fields = ["created_at"]
    date_hierarchy = "created_at"


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = [
        "patient",
        "weight_kg",
        "systolic_bp",
        "diastolic_bp",
        "heart_rate_bpm",
        "measured_at",
    ]
    list_filter = ["measured_at"]
    search_fields = ["patient__name"]
    readonly_fields = ["measured_at"]
    date_hierarchy = "measured_at"
    autocomplete_fields = ["patient"]


@admin.register(QueueTicket)
class QueueTicketAdmin(admin.ModelAdmin):
    list_display = ["queue_number", "patient", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["queue_number", "patient__name", "qr_code_data"]
    readonly_fields = ["qr_code_data", "created_at"]
    date_hierarchy = "created_at"
    autocomplete_fields = ["patient"]
    list_editable = ["is_active"]


class SiteConfigurationForm(forms.ModelForm):
    openai_api_key = forms.CharField(
        label="New OpenAI API key",
        required=False,
        strip=True,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "off"}),
        help_text="Leave blank to keep the current key. The key is stored encrypted and is never shown again.",
    )
    clear_openai_api_key = forms.BooleanField(
        label="Remove the stored OpenAI API key", required=False
    )

    class Meta:
        model = SiteConfiguration
        fields = []

    def clean_openai_api_key(self):
        key = self.cleaned_data["openai_api_key"]
        if key and not key.startswith("sk-"):
            raise forms.ValidationError("OpenAI API keys start with \"sk-\".")
        return key

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("openai_api_key") and cleaned.get("clear_openai_api_key"):
            raise forms.ValidationError("Enter a new key or remove the current one, not both.")
        return cleaned


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    form = SiteConfigurationForm
    readonly_fields = ["current_openai_api_key", "updated_at"]
    fieldsets = [
        (
            "OpenAI",
            {"fields": ["current_openai_api_key", "openai_api_key", "clear_openai_api_key"]},
        ),
        (
            "Server secrets",
            {
                "fields": ["updated_at"],
                "description": (
                    "Django SECRET_KEY and FIELD_ENCRYPTION_KEY are generated at install time "
                    "and kept in the server's .env file. They cannot be changed here: Django "
                    "needs them before the database is available, and changing them signs "
                    "everyone out or makes stored secrets unreadable."
                ),
            },
        ),
    ]

    @admin.display(description="Current OpenAI API key")
    def current_openai_api_key(self, obj):
        return obj.openai_api_key_hint or "Not set"

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteConfiguration.load()
        return redirect(reverse("admin:kiosk_siteconfiguration_change", args=[obj.pk]))

    def save_model(self, request, obj, form, change):
        if form.cleaned_data.get("clear_openai_api_key"):
            obj.openai_api_key = ""
        elif form.cleaned_data.get("openai_api_key"):
            obj.openai_api_key = form.cleaned_data["openai_api_key"]
        super().save_model(request, obj, form, change)
