"""Registration, patient self-service form, and the doctor's workspace."""

import datetime as dt
import logging

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView
from django_ratelimit.decorators import ratelimit

from .forms import (
    PROFILE_FIELDS,
    DiagnosisForm,
    PatientProfileForm,
    PatientSelfForm,
    PrescriptionFormSet,
    allergy_conflicts,
)
from . import queue
from . import ai
from .models import AuditEvent, Measurement, Patient, PatientSubmission, StaffProfile, Visit, get_openai_api_key
from .roles import CapabilityRequiredMixin, DoctorRequiredMixin, StaffAreaMixin, can, is_doctor
from .portal_views import render_invite
from .views import latest_vitals

logger = logging.getLogger(__name__)

# How long after a check-in the patient may still complete their details.
SELF_SERVICE_DAYS = 7
NULLABLE_FIELDS = {"has_drug_allergy", "height_cm", "date_of_birth"}


def _record_weight(patient, visit, weight, source):
    if weight:
        Measurement.objects.create(patient=patient, visit=visit, weight_kg=weight, source=source)


def _changed_fields(before, patient):
    return [f for f in PROFILE_FIELDS if before.get(f) != getattr(patient, f)]


# --- Registration (staff) ----------------------------------------------------------


class PatientRegisterView(CapabilityRequiredMixin, View):
    capability = "register_patients"
    template_name = "kiosk/patient_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": PatientProfileForm(), "creating": True})

    def post(self, request):
        form = PatientProfileForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "creating": True})
        with transaction.atomic():
            patient = form.save()
            _record_weight(patient, None, form.cleaned_data.get("weight_kg"), Measurement.SOURCE_MANUAL)
            AuditEvent.record(request.user, "patient.registered", patient=patient)
        messages.success(request, f"{patient.name} registered. Patient ID: {patient.patient_id}")
        return redirect("kiosk:patient-detail", patient.pk)


class PatientEditView(StaffAreaMixin, View):
    template_name = "kiosk/patient_form.html"

    def get(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk)
        return render(request, self.template_name, {"form": PatientProfileForm(instance=patient), "patient": patient})

    def post(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk)
        before = {f: getattr(patient, f) for f in PROFILE_FIELDS}
        form = PatientProfileForm(request.POST, instance=patient)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "patient": patient})
        with transaction.atomic():
            patient = form.save()
            _record_weight(patient, None, form.cleaned_data.get("weight_kg"), Measurement.SOURCE_MANUAL)
            AuditEvent.record(request.user, "patient.updated", patient=patient, fields=_changed_fields(before, patient))
        messages.success(request, "Patient details saved.")
        return redirect("kiosk:patient-detail", patient.pk)


# --- Patient self-service (public, via the ticket QR code) --------------------------------


@method_decorator(never_cache, name="dispatch")
@method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True), name="post")
class VisitTokenView(View):
    """Target of the ticket QR code.

    Staff who are logged in go to the visit. Anyone else gets the form to
    complete the patient's registration; it never shows stored data.
    """

    template_name = "kiosk/registration_public.html"

    def _visit(self, token):
        return get_object_or_404(Visit.objects.select_related("patient"), token=token)

    def _expired(self, visit):
        return visit.created_at < timezone.now() - dt.timedelta(days=SELF_SERVICE_DAYS)

    def get(self, request, token):
        visit = self._visit(token)
        if can(request.user, "staff_area"):
            return redirect("kiosk:visit-detail", visit.pk)
        if self._expired(visit):
            return render(request, self.template_name, {"expired": True, "visit": visit})
        form = PatientSelfForm(initial={"name": visit.patient.name})
        return render(request, self.template_name, {"form": form, "visit": visit})

    def post(self, request, token):
        visit = self._visit(token)
        if self._expired(visit):
            return render(request, self.template_name, {"expired": True, "visit": visit})
        # A fresh Patient instance: validation must not read or change stored data.
        form = PatientSelfForm(request.POST, instance=Patient(pk=None))
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "visit": visit})
        PatientSubmission.objects.filter(patient=visit.patient, status=PatientSubmission.PENDING).update(
            status=PatientSubmission.REJECTED, review_note="Replaced by a newer submission", reviewed_at=timezone.now()
        )
        PatientSubmission.objects.create(patient=visit.patient, visit=visit, data=form.submission_data())
        AuditEvent.record(None, "submission.received", visit=visit)
        return render(request, self.template_name, {"submitted": True, "visit": visit})


# --- Review of patient submissions (staff) -------------------------------------------------


class SubmissionListView(CapabilityRequiredMixin, TemplateView):
    capability = "review_registrations"
    template_name = "kiosk/submissions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        for submission in PatientSubmission.objects.filter(status=PatientSubmission.PENDING).select_related("patient", "visit"):
            form = PatientProfileForm(instance=submission.patient)
            fields = []
            for name in PROFILE_FIELDS + ["weight_kg"]:
                field = form.fields[name]
                new = submission.data.get(name)
                old = getattr(submission.patient, name, None) if name != "weight_kg" else None
                fields.append({"label": field.label, "old": _display(name, old), "new": _display(name, new), "changed": _display(name, old) != _display(name, new)})
            rows.append({"submission": submission, "fields": fields})
        context["rows"] = rows
        context["recent"] = PatientSubmission.objects.exclude(status=PatientSubmission.PENDING).select_related("patient", "reviewed_by")[:10]
        return context


def _display(name, value):
    if value in (None, ""):
        return "—"
    if name == "has_drug_allergy":
        return "Yes" if value else "No"
    if name == "id_type":
        return dict(Patient.ID_TYPE_CHOICES).get(value, value)
    if isinstance(value, dt.date):
        return value.strftime("%d %b %Y")
    if name == "date_of_birth":
        return dt.date.fromisoformat(value).strftime("%d %b %Y")
    return str(value)


class SubmissionReviewView(CapabilityRequiredMixin, View):
    capability = "review_registrations"

    def post(self, request, pk):
        submission = get_object_or_404(PatientSubmission, pk=pk, status=PatientSubmission.PENDING)
        patient = submission.patient
        if request.POST.get("decision") == "approve":
            data = dict(submission.data)
            weight = data.pop("weight_kg", None)
            if data.get("date_of_birth"):
                data["date_of_birth"] = dt.date.fromisoformat(data["date_of_birth"])
            before = {f: getattr(patient, f) for f in PROFILE_FIELDS}
            with transaction.atomic():
                for name in PROFILE_FIELDS:
                    value = data.get(name)
                    if value is None and name not in NULLABLE_FIELDS:
                        value = ""
                    setattr(patient, name, value)
                patient.save()
                _record_weight(patient, submission.visit, weight, Measurement.SOURCE_PATIENT)
                submission.status = PatientSubmission.APPROVED
                AuditEvent.record(request.user, "submission.approved", patient=patient, fields=_changed_fields(before, patient))
            submission.reviewed_by = request.user
            submission.reviewed_at = timezone.now()
            submission.save()
            # Same as for staff: hand the patient a one-time link to their own account.
            return render_invite(request, patient, approved=True)
        else:
            submission.status = PatientSubmission.REJECTED
            submission.review_note = request.POST.get("note", "")[:200]
            AuditEvent.record(request.user, "submission.rejected", patient=patient, note=submission.review_note)
            messages.info(request, f"Submission for {patient.name} rejected.")
        submission.reviewed_by = request.user
        submission.reviewed_at = timezone.now()
        submission.save()
        return redirect("kiosk:submissions")


# --- Merging duplicate patients (staff) ---------------------------------------------------


class PatientMergeView(CapabilityRequiredMixin, View):
    """Move everything from a duplicate record into the patient's main record."""

    capability = "merge_patients"
    template_name = "kiosk/patient_merge.html"

    def get(self, request, pk):
        return render(request, self.template_name, {"patient": get_object_or_404(Patient, pk=pk)})

    def post(self, request, pk):
        source = get_object_or_404(Patient, pk=pk)
        target_id = "".join(request.POST.get("target", "").split()).upper()
        target = Patient.objects.filter(patient_id=target_id).exclude(pk=source.pk).first()
        if target is None:
            messages.error(request, "Enter the Patient ID of a different, existing patient.")
            return render(request, self.template_name, {"patient": source})
        with transaction.atomic():
            for name in PROFILE_FIELDS:
                if getattr(target, name) in (None, "") and getattr(source, name) not in (None, ""):
                    setattr(target, name, getattr(source, name))
            target.save()
            source.visits.update(patient=target)
            source.measurements.update(patient=target)
            source.submissions.update(patient=target)
            source.audit_events.update(patient=target)
            AuditEvent.record(request.user, "patient.merged", patient=target, merged_patient_id=source.patient_id, merged_name=source.name)
            source.delete()
        messages.success(request, f"Merged {source.patient_id} into {target.name} ({target.patient_id}).")
        return redirect("kiosk:patient-detail", target.pk)


# --- Doctor ---------------------------------------------------------------------------------


class DoctorQueueView(CapabilityRequiredMixin, TemplateView):
    capability = "consultations"
    template_name = "kiosk/doctor_queue.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = queue.todays_queue().select_related(
            "patient", "doctor__profile", "requested_doctor__profile", "cancelled_by"
        ).prefetch_related("measurements")

        def rows(visits):
            return [{"visit": v, "vitals": latest_vitals(v.measurements.all())} for v in visits]

        context["mine_in_progress"] = rows(today.filter(status=Visit.IN_CONSULTATION, doctor=user))
        context["mine_called"] = rows(today.filter(status=Visit.CALLED, doctor=user))
        waiting = queue.waiting_in_order()
        on_duty = {d.pk for d, _ in queue.doctors_on_duty()}
        waiting_rows = rows(today.filter(pk__in=[v.pk for v in waiting]))
        order = {v.pk: i for i, v in enumerate(waiting)}
        waiting_rows.sort(key=lambda r: order[r["visit"].pk])
        for row in waiting_rows:
            row["line"] = queue.chosen_doctor(row["visit"], on_duty)  # None: first available doctor
        context["waiting"] = waiting_rows
        others = today.exclude(status=Visit.WAITING).exclude(status__in=[Visit.CALLED, Visit.IN_CONSULTATION], doctor=user)
        if is_doctor(user):
            # Doctors see only their own line (patients who chose them or any
            # doctor) and their own patients, never other doctors' patients.
            context["my_line"] = [r for r in waiting_rows if r["line"] is None or r["line"].pk == user.pk]
            others = others.filter(Q(doctor=user) | Q(doctor__isnull=True, requested_doctor=user))
        context["others"] = rows(others.order_by("-called_at", "queue_number"))
        context["not_arrived"] = queue.not_arrived(user if is_doctor(user) else None)
        context["is_doctor"] = is_doctor(user)
        context["room"] = StaffProfile.room_for(user)
        profile = StaffProfile.objects.filter(user=user).first()
        context["on_duty"] = profile.on_duty if profile else True
        context["has_room"] = bool(profile and profile.room)
        return context


@method_decorator(ratelimit(key="user", rate="10/m", method="POST", block=True), name="post")
class VisitAISummaryView(DoctorRequiredMixin, View):
    """Generate (or regenerate) the AI pre-consultation summary for the doctor."""

    def post(self, request, pk):
        visit = get_object_or_404(Visit.objects.select_related("patient"), pk=pk)
        try:
            text, model = ai.generate_summary(visit)
        except ai.AIError as exc:
            messages.error(request, str(exc))
            return redirect("kiosk:visit-detail", visit.pk)
        visit.ai_summary = text
        visit.ai_summary_model = model[:60]
        visit.ai_summary_at = timezone.now()
        visit.ai_summary_by = request.user
        visit.save(update_fields=["ai_summary", "ai_summary_model", "ai_summary_at", "ai_summary_by"])
        AuditEvent.record(request.user, "visit.ai_summary", visit=visit, model=visit.ai_summary_model)
        return redirect(reverse("kiosk:visit-detail", args=[visit.pk]) + "#ai-summary")


class VisitDetailView(StaffAreaMixin, View):
    """The doctor's workspace for one visit; read-only for other staff."""

    template_name = "kiosk/visit_detail.html"

    def _context(self, request, visit, form=None, formset=None, conflicts=None):
        patient = visit.patient
        measurements = list(patient.measurements.order_by("-measured_at"))
        oldest_first = list(reversed(measurements))
        return {
            "visit": visit,
            "patient": patient,
            "vitals": latest_vitals(visit.measurements.order_by("-measured_at")),
            "previous_visits": patient.visits.exclude(pk=visit.pk).prefetch_related("prescriptions").select_related("doctor")[:10],
            "can_edit": is_doctor(request.user),
            "ai_available": bool(get_openai_api_key()),
            "form": form or DiagnosisForm(instance=visit),
            "formset": formset or PrescriptionFormSet(instance=visit),
            "conflicts": conflicts or [],
            "pending_submission": patient.submissions.filter(status=PatientSubmission.PENDING).exists(),
            "chart_data": {
                "bp": [
                    {"t": m.measured_at.isoformat(), "systolic": m.systolic_bp, "diastolic": m.diastolic_bp, "pulse": m.heart_rate_bpm}
                    for m in oldest_first if m.systolic_bp is not None and m.diastolic_bp is not None
                ],
                "weight": [{"t": m.measured_at.isoformat(), "weight": m.weight_kg} for m in oldest_first if m.weight_kg is not None],
            },
        }

    def get(self, request, pk):
        visit = get_object_or_404(Visit.objects.select_related("patient", "doctor"), pk=pk)
        return render(request, self.template_name, self._context(request, visit))

    def post(self, request, pk):
        visit = get_object_or_404(Visit.objects.select_related("patient"), pk=pk)
        if not is_doctor(request.user):
            messages.error(request, "Only doctors can record a diagnosis or prescription.")
            return redirect("kiosk:visit-detail", visit.pk)

        form = DiagnosisForm(request.POST, instance=visit)
        formset = PrescriptionFormSet(request.POST, instance=visit)
        if not (form.is_valid() and formset.is_valid()):
            return render(request, self.template_name, self._context(request, visit, form, formset))

        drugs = [f.cleaned_data["drug"] for f in formset.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]
        conflicts = allergy_conflicts(visit.patient, drugs)
        if conflicts and not request.POST.get("confirm_allergy"):
            return render(request, self.template_name, self._context(request, visit, form, formset, conflicts))

        completing = "complete" in request.POST or "complete_next" in request.POST
        with transaction.atomic():
            visit = form.save(commit=False)
            visit.doctor = request.user
            visit.diagnosed_at = timezone.now()
            visit.save()
            if completing:
                queue.complete(visit, request.user)
            items = formset.save(commit=False)
            for obj in formset.deleted_objects:
                obj.delete()
            for item in items:
                if not item.pk:
                    item.created_by = request.user
                item.allergy_override = item.drug in conflicts
                item.save()
            AuditEvent.record(
                request.user,
                "visit.completed" if visit.status == Visit.COMPLETED else "visit.diagnosed",
                visit=visit,
                diagnosis=visit.diagnosis,
                code=visit.diagnosis_code,
                drugs=[p.drug for p in visit.prescriptions.all()],
                allergy_overrides=conflicts,
            )
        if not completing:
            messages.success(request, "Diagnosis and prescription saved.")
            return redirect("kiosk:visit-detail", visit.pk)
        if "complete_next" in request.POST:
            nxt = queue.call_next(request.user)
            messages.success(
                request,
                f"Consultation completed. Called {nxt.queue_number} to {nxt.room}." if nxt else "Consultation completed. Nobody else is waiting.",
            )
        else:
            messages.success(request, "Consultation completed.")
        return redirect("kiosk:doctor-queue")


class PrescriptionPrintView(StaffAreaMixin, TemplateView):
    template_name = "kiosk/prescription_print.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visit = get_object_or_404(Visit.objects.select_related("patient", "doctor"), pk=self.kwargs["pk"])
        context["visit"] = visit
        context["patient"] = visit.patient
        context["items"] = visit.prescriptions.all()
        return context


def legacy_ticket_redirect(request, qr_code):
    """Old QR codes pointed at /ticket/<uuid>/."""
    return redirect("kiosk:visit-token", qr_code)
