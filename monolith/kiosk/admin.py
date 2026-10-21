from django import forms
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .models import (
    AuditEvent,
    BookingRequest,
    DeviceReading,
    Measurement,
    Patient,
    PatientSubmission,
    PrescriptionItem,
    Review,
    Service,
    SiteConfiguration,
    StaffProfile,
    Visit,
)

admin.site.site_header = "AIVIN administration"
admin.site.site_title = "AIVIN admin"
admin.site.index_title = "AIVIN — AI-Vital Intake"


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["patient_id", "name", "date_of_birth", "phone", "has_drug_allergy", "created_at"]
    search_fields = ["patient_id", "name", "phone"]
    list_filter = ["has_drug_allergy", "created_at"]
    readonly_fields = ["patient_id", "created_at", "updated_at"]
    date_hierarchy = "created_at"


class PrescriptionInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 0
    readonly_fields = ["created_by", "created_at"]


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ["queue_number", "queue_date", "patient", "status", "doctor", "created_at"]
    list_filter = ["status", "queue_date"]
    search_fields = ["queue_number", "patient__name", "patient__patient_id"]
    readonly_fields = ["token", "created_at", "diagnosed_at"]
    autocomplete_fields = ["patient"]
    inlines = [PrescriptionInline]


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "room"]


@admin.register(PatientSubmission)
class PatientSubmissionAdmin(admin.ModelAdmin):
    list_display = ["patient", "status", "submitted_at", "reviewed_by"]
    list_filter = ["status"]
    readonly_fields = ["patient", "visit", "data", "submitted_at", "reviewed_by", "reviewed_at"]


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "patient", "visit"]
    list_filter = ["action"]
    readonly_fields = [f.name for f in AuditEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = [
        "patient",
        "weight_kg",
        "systolic_bp",
        "diastolic_bp",
        "heart_rate_bpm",
        "source",
        "measured_at",
    ]
    list_filter = ["source", "measured_at"]
    search_fields = ["patient__name", "patient__patient_id"]
    readonly_fields = ["measured_at"]
    date_hierarchy = "measured_at"
    autocomplete_fields = ["patient", "visit"]


@admin.register(DeviceReading)
class DeviceReadingAdmin(admin.ModelAdmin):
    list_display = ["kind", "device_model", "measured_at", "systolic_bp", "diastolic_bp", "heart_rate_bpm", "weight_kg", "measurement"]
    list_filter = ["kind", "device_model", "measured_at"]
    readonly_fields = [f.name for f in DeviceReading._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


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


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "price_sgd", "price_unit", "price_confirmed", "is_featured", "is_bookable", "is_active", "sort_order"]
    list_editable = ["price_sgd", "price_confirmed", "is_featured", "is_bookable", "is_active", "sort_order"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = ["name", "service", "preferred_date", "preferred_time", "status", "created_at"]
    list_filter = ["status", "service"]
    search_fields = ["name", "phone", "email"]
    readonly_fields = ["consent_at", "created_at", "handled_by", "handled_at"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["patient", "rating", "status", "created_at"]
    list_filter = ["status", "rating"]
    readonly_fields = ["visit", "patient", "created_at", "moderated_by", "moderated_at"]
