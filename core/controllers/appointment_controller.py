from datetime import date, timedelta

from fastapi import HTTPException, status
from odmantic.exceptions import DuplicateKeyError as ODMDuplicateKeyError
from pymongo.errors import DuplicateKeyError as PyMongoDuplicateKeyError

from bson import ObjectId
from common.logger import get_logger
from core.apis.schemas.appointment_schema import (
    AppointmentResponse,
    BookAppointmentRequest,
    CancelResponse,
)
from core.constants import MAX_BOOKING_DAYS, MAX_PATIENTS_PER_SLOT, is_valid_slot
from core.cruds.appointment_crud import (
    cancel_appointment_by_id,
    count_active_appointments_for_slot,
    count_patient_active_appointments_for_date,
    create_appointment,
    find_all_appointments_by_patient,
    find_appointment_by_patient_and_id,
)
from core.cruds.doctor_profile_crud import (
    find_profile_by_id,
    find_profile_by_user_id,
)
from core.database.database import get_engine
from core.models.appointment_model import AppointmentModel
from core.models.doctor_profile_model import DoctorProfileModel

logger = get_logger(__name__)


class AppointmentController:
    """Controller handling patient appointment booking, listing, and cancellation."""

    async def book_appointment(
        self,
        booking_request: BookAppointmentRequest,
        patient_id: str = "",
        patient_name: str = "",
        authenticated_user_details: dict = None,
    ) -> AppointmentResponse:
        """Process appointment booking request applying all 4 validation gates."""
        engine = get_engine()
        if authenticated_user_details:
            patient_id = authenticated_user_details.get("user_id") or patient_id
            patient_name = authenticated_user_details.get("name") or patient_name

        # ── Tenant + doctor scope from the request body ───────────────────────
        # Patients have no hospital_id in their JWT (they choose which hospital
        # to book at). hospital_id and doctor_id come from the body because the
        # patient is SELECTING a destination, not asserting identity.
        # Patient identity (patient_id) always comes from the JWT above.
        hospital_id: str = booking_request.hospital_id
        doctor_id: str = booking_request.doctor_id

        # ── Gate 1: Date format ───────────────────────────────────────────────
        try:
            booking_date = date.fromisoformat(booking_request.date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD.",
            )

        # ── Gate 1b: Date range ───────────────────────────────────────────────
        today = date.today()
        max_date = today + timedelta(days=MAX_BOOKING_DAYS)

        if booking_date < today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot book an appointment for a past date.",
            )

        if booking_date > max_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Appointments can only be booked up to {MAX_BOOKING_DAYS} days in advance.",
            )

        # ── Gate 1c: Doctor Availability Check ────────────────────────────────
        profile = await find_profile_by_id(engine, hospital_id, doctor_id)
        if not profile:
            try:
                profile_obj_id = ObjectId(doctor_id)
                profile = await engine.find_one(DoctorProfileModel, DoctorProfileModel.id == profile_obj_id)
            except Exception:
                profile = await find_profile_by_user_id(engine, doctor_id)
        if profile and booking_request.date in profile.unavailable_dates:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Doctor is unavailable on this date. Please select another date for your appointment.",
            )

        # ── Gate 2: Valid slot string ─────────────────────────────────────────
        if not is_valid_slot(booking_request.slot):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid appointment slot. Please select a valid slot.",
            )

        # ── Gate 3: One appointment per patient per day ───────────────────────
        # Enforces that a single patient cannot book more than one active appointment
        # for the same day anywhere on the platform.
        patient_same_day_count = await count_patient_active_appointments_for_date(
            engine, patient_id, booking_request.date
        )
        if patient_same_day_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have an active appointment for this date. Patients can only book one appointment per day.",
            )

        # ── Gate 4: Slot capacity per doctor (scoped by hospital + doctor) ────
        # In the multi-tenant model, slot capacity is per (hospital, doctor, date, slot).
        # Two doctors at the same hospital can have independent bookings at 10:00.
        active_count = await count_active_appointments_for_slot(
            engine, hospital_id, doctor_id, booking_request.date, booking_request.slot
        )
        if active_count >= MAX_PATIENTS_PER_SLOT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This time slot is already fully booked. Please select another slot.",
            )

        new_appointment = AppointmentModel(
            hospital_id=hospital_id,
            doctor_id=doctor_id,
            patient_id=patient_id,
            patient_name=patient_name,
            date=booking_request.date,
            slot=booking_request.slot,
            reason=booking_request.reason,
            temperature=booking_request.temperature,
            symptoms=booking_request.symptoms,
            is_cancelled=False,
        )

        try:
            saved = await create_appointment(engine, new_appointment)
        except (PyMongoDuplicateKeyError, ODMDuplicateKeyError):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This time slot was just booked by another patient. Please select another slot.",
            )

        return AppointmentResponse(
            appointment_id=str(saved.id),
            patient_name=saved.patient_name,
            date=saved.date,
            slot=saved.slot,
            reason=saved.reason,
            temperature=saved.temperature,
            symptoms=[s.value for s in saved.symptoms],
            status=saved.status.value if hasattr(saved.status, "value") else str(saved.status or "pending"),
            is_cancelled=saved.is_cancelled,
            created_at=saved.created_at.isoformat(),
            message="Appointment booked successfully.",
        )

    async def list_my_appointments(
        self, authenticated_user_details: dict
    ) -> list[AppointmentResponse]:
        engine = get_engine()
        patient_id = authenticated_user_details.get("user_id")

        if not patient_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
            )

        # Cross-tenant lookup: patients see ALL their appointments across all
        # hospitals. No hospital_id scope applied — the patient_id is the only
        # ownership filter.
        appointments = await find_all_appointments_by_patient(engine, patient_id)

        from core.cruds.prescription_crud import find_prescription_by_appointment

        results = []
        for app in appointments:
            p = await find_prescription_by_appointment(engine, str(app.id))
            appt_status = app.status.value if hasattr(app.status, "value") else str(app.status or "pending")
            results.append(
                AppointmentResponse(
                    appointment_id=str(app.id),
                    patient_name=app.patient_name,
                    date=app.date,
                    slot=app.slot,
                    reason=app.reason,
                    temperature=app.temperature,
                    symptoms=[s.value for s in app.symptoms],
                    status=appt_status,
                    prescription_id=str(p.id) if p else None,
                    pdf_url=p.pdf_url if p else None,
                    is_cancelled=app.is_cancelled,
                    cancellation_reason=app.cancellation_reason,
                    created_at=app.created_at.isoformat(),
                )
            )
        return results

    async def cancel_appointment(
        self, appointment_id: str, authenticated_user_details: dict
    ) -> CancelResponse:
        engine = get_engine()
        patient_id = authenticated_user_details.get("user_id")

        if not patient_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload.",
            )

        # Ownership-scoped lookup: find by (appointment_id, patient_id).
        # No hospital_id needed — the patient_id check is sufficient to ensure
        # they can only cancel their own appointments across any hospital.
        appointment = await find_appointment_by_patient_and_id(
            engine, patient_id, appointment_id
        )
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found or does not belong to you.",
            )

        if appointment.is_cancelled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This appointment is already cancelled.",
            )

        await cancel_appointment_by_id(engine, appointment)

        return CancelResponse(
            appointment_id=appointment_id,
            message="Appointment cancelled successfully. Slot is now available.",
        )


# Backward compatibility wrappers
book_appointment_controller = AppointmentController().book_appointment
list_my_appointments_controller = AppointmentController().list_my_appointments
cancel_appointment_controller = AppointmentController().cancel_appointment
