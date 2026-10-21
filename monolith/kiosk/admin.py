from django.contrib import admin

from .models import Measurement, Patient, QueueTicket


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
