from datetime import date, timedelta

from fastapi import HTTPException, status

from common.logger import get_logger
from core.apis.schemas.doctor_schema import (
    DoctorInfoResponse,
    DoctorScheduleResponse,
    DoctorStatsResponse,
    DoctorUnavailabilityRequest,
    DoctorUnavailabilityResponse,
    FreeSlotsResponse,
    ScheduleEntryResponse,
)
from core.constants import DOCTOR_INFO, MAX_BOOKING_DAYS, calculate_free_slots
from core.cruds.appointment_crud import (
    count_today_appointments,
    count_upcoming_appointments,
    find_booked_slots_by_date,
    find_schedule_by_date,
)
from core.cruds.doctor_profile_crud import (
    find_profile_by_id,
    find_profile_by_user_and_hospital,
    find_profile_by_user_id,
    update_doctor_unavailable_dates,
)
from core.cruds.user_crud import count_all_patients
from core.database.database import get_engine
from core.models.appointment_model import AppointmentModel
from core.models.doctor_profile_model import DoctorProfileModel

logger = get_logger(__name__)


class DoctorController:
    """Consolidated controller handling clinic profile, free slots, doctor schedule, statistics, and unavailability management."""

    # ─── Public Clinic Operations ─────────────────────────────────────────────

    async def get_doctor_info(self) -> DoctorInfoResponse:
        """Retrieve static profile information about the clinic and doctor."""
        logger.info("Doctor info requested")
        return DoctorInfoResponse(**DOCTOR_INFO)

    async def get_free_slots(
        self, requested_date: str, hospital_id: str = "", doctor_id: str = ""
    ) -> FreeSlotsResponse:
        """Calculate and return free appointment slots for a specified date."""
        logger.info("Free slots requested for date: %s", requested_date)
        engine = get_engine()

        try:
            query_date = date.fromisoformat(requested_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD.",
            )

        today = date.today()
        max_date = today + timedelta(days=MAX_BOOKING_DAYS)

        if query_date < today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot query slots for a past date.",
            )

        if query_date > max_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Slots can only be viewed up to {MAX_BOOKING_DAYS} days in advance.",
            )

        # Check if doctor is marked as unavailable on requested_date
        if doctor_id:
            profile = await find_profile_by_id(engine, hospital_id, doctor_id)
            if not profile:
                profile = await find_profile_by_user_id(engine, doctor_id)
            if profile and requested_date in profile.unavailable_dates:
                logger.info("Doctor profile '%s' is unavailable on date: %s", doctor_id, requested_date)
                return FreeSlotsResponse(
                    date=requested_date,
                    available_slots=[],
                    total_available=0,
                )

        booked_slots = await find_booked_slots_by_date(
            engine, hospital_id, doctor_id, requested_date
        )
        free_slots = calculate_free_slots(booked_slots)

        return FreeSlotsResponse(
            date=requested_date,
            available_slots=free_slots,
            total_available=len(free_slots),
        )

    # ─── Doctor Dashboard Operations ──────────────────────────────────────────

    async def get_schedule(
        self, requested_date: str, hospital_id: str = "", doctor_user_id: str = ""
    ) -> DoctorScheduleResponse:
        """Fetch all scheduled and cancelled appointments for the doctor on a given date."""
        engine = get_engine()

        try:
            date.fromisoformat(requested_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD.",
            )

        is_unavailable = False
        if doctor_user_id:
            profile = await find_profile_by_user_id(engine, doctor_user_id)
            if profile and requested_date in profile.unavailable_dates:
                is_unavailable = True

        appointments = await find_schedule_by_date(
            engine, hospital_id, requested_date
        )

        schedule_entries = [
            ScheduleEntryResponse(
                appointment_id=str(appointment.id),
                slot=appointment.slot,
                patient_name=appointment.patient_name,
                reason=appointment.reason,
                temperature=appointment.temperature,
                symptoms=[symptom.value for symptom in appointment.symptoms],
                is_cancelled=appointment.is_cancelled,
                cancellation_reason=appointment.cancellation_reason,
            )
            for appointment in appointments
        ]

        return DoctorScheduleResponse(
            date=requested_date,
            is_unavailable=is_unavailable,
            total_appointments=len(schedule_entries),
            schedule=schedule_entries,
        )

    async def toggle_unavailability(
        self, doctor_user_id: str, hospital_id: str, payload: DoctorUnavailabilityRequest
    ) -> DoctorUnavailabilityResponse:
        """Mark or unmark a specific date as unavailable (off-day) for a doctor."""
        engine = get_engine()
        target_date = payload.date.strip()

        try:
            date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD.",
            )

        profile = None
        if hospital_id:
            profile = await find_profile_by_user_and_hospital(engine, hospital_id, doctor_user_id)
        if not profile:
            profile = await find_profile_by_user_id(engine, doctor_user_id)

        if not profile:
            profile = DoctorProfileModel(
                user_id=doctor_user_id,
                hospital_id=hospital_id or "60d5ecb8b5c9c80015f8e999",
                specialization="General Physician",
                consultation_fee="Rs. 300",
            )
            profile = await engine.save(profile)

        unavailable_dates = list(profile.unavailable_dates)
        cancelled_count = 0

        if payload.is_unavailable:
            if target_date not in unavailable_dates:
                unavailable_dates.append(target_date)

            # Soft-cancel existing active appointments for this doctor on target_date
            doctor_profile_id = str(profile.id)
            active_appointments = await engine.find(
                AppointmentModel,
                (AppointmentModel.date == target_date)
                & (AppointmentModel.is_cancelled == False)
                & (
                    (AppointmentModel.doctor_id == doctor_profile_id)
                    | (AppointmentModel.doctor_id == doctor_user_id)
                ),
            )

            cancellation_msg = "Appointment cancelled due to doctor unavailability. Please reschedule for the next available day."
            for appt in active_appointments:
                appt.is_cancelled = True
                appt.cancellation_reason = cancellation_msg
                await engine.save(appt)
                cancelled_count += 1

            msg = f"Date {target_date} marked as unavailable. {cancelled_count} active appointment(s) cancelled and notified."
            logger.info(
                "Doctor '%s' marked date '%s' as unavailable — %d appointments cancelled",
                doctor_user_id,
                target_date,
                cancelled_count,
            )
        else:
            if target_date in unavailable_dates:
                unavailable_dates.remove(target_date)
            msg = f"Date {target_date} marked as available."
            logger.info("Doctor '%s' marked date '%s' as available", doctor_user_id, target_date)

        updated_profile = await update_doctor_unavailable_dates(
            engine, profile, unavailable_dates
        )

        return DoctorUnavailabilityResponse(
            date=target_date,
            is_unavailable=payload.is_unavailable,
            unavailable_dates=updated_profile.unavailable_dates,
            cancelled_appointments_count=cancelled_count,
            message=msg,
        )

    async def get_unavailability_list(
        self, doctor_user_id: str, hospital_id: str = ""
    ) -> DoctorUnavailabilityResponse:
        """Get the full list of unavailable dates for a doctor."""
        engine = get_engine()
        profile = None
        if hospital_id:
            profile = await find_profile_by_user_and_hospital(engine, hospital_id, doctor_user_id)
        if not profile:
            profile = await find_profile_by_user_id(engine, doctor_user_id)

        if not profile:
            return DoctorUnavailabilityResponse(
                date=date.today().isoformat(),
                is_unavailable=False,
                unavailable_dates=[],
                cancelled_appointments_count=0,
                message="No profile found.",
            )

        return DoctorUnavailabilityResponse(
            date=date.today().isoformat(),
            is_unavailable=False,
            unavailable_dates=profile.unavailable_dates,
            cancelled_appointments_count=0,
            message="Doctor unavailability list retrieved.",
        )

    async def get_stats(self, hospital_id: str = "") -> DoctorStatsResponse:
        """Calculate clinic stats (total patients, today's visits, upcoming visits)."""
        engine = get_engine()
        today_date_string = date.today().isoformat()

        total_patients = await count_all_patients(engine)
        todays_visits = await count_today_appointments(
            engine, hospital_id, today_date_string
        )
        upcoming_visits = await count_upcoming_appointments(
            engine, hospital_id, today_date_string
        )

        return DoctorStatsResponse(
            total_registered_patients=total_patients,
            todays_visit_count=todays_visits,
            upcoming_visit_count=upcoming_visits,
        )


# Alias for backward compatibility
ClinicController = DoctorController

# Backward compatibility function wrappers
get_doctor_info_controller = DoctorController().get_doctor_info
get_free_slots_controller = DoctorController().get_free_slots
get_doctor_schedule_controller = DoctorController().get_schedule
get_doctor_stats_controller = DoctorController().get_stats
