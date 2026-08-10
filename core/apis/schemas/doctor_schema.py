"""
─────────────────────────────────────────────────────────────────────────────
File        : core/apis/schemas/doctor_schema.py
Purpose     : Pydantic response schemas for doctor dashboard and public
              clinic information endpoints.

Responsibilities:
    - Define structured response models for doctor-only endpoints
    - Define response models for public GET /doctor-info and GET /free-slots
    - Provide Swagger-ready field descriptions

Used By:
    - core/apis/routes/doctor_router.py
    - core/apis/routes/clinic_router.py
    - core/controllers/doctor_controller.py
    - core/controllers/clinic_controller.py
─────────────────────────────────────────────────────────────────────────────
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DoctorInfoResponse(BaseModel):
    """
    Response schema for GET /doctor-info.

    Returns static clinic and doctor profile information.
    This endpoint is publicly accessible without authentication.
    """

    doctor_name: str = Field(..., description="Full name of the doctor.")
    specialization: str = Field(..., description="Medical specialization.")
    clinic_name: str = Field(..., description="Name of the clinic.")
    consultation_fee: str = Field(..., description="Consultation fee per visit.")
    morning_hours: str = Field(..., description="Morning consultation hours.")
    evening_hours: str = Field(..., description="Evening consultation hours.")
    slot_duration_minutes: int = Field(..., description="Duration of each appointment slot in minutes.")
    total_slots_per_day: int = Field(..., description="Total number of available slots per day.")
    max_patients_per_slot: int = Field(1, description="Maximum number of patients allowed per slot.")
    languages_spoken: List[str] = Field(..., description="Languages spoken by the doctor.")
    address: str = Field(..., description="Clinic address.")
    phone: str = Field(..., description="Clinic contact number.")


class FreeSlotsResponse(BaseModel):
    """
    Response schema for GET /free-slots.

    Returns the list of available (unbooked, non-cancelled) appointment
    slots for the requested date.
    """

    date: str = Field(..., description="The queried date in YYYY-MM-DD format.")
    available_slots: List[str] = Field(
        ..., description="List of free time slots in HH:MM format."
    )
    total_available: int = Field(
        ..., description="Count of free slots remaining for the date."
    )


class ScheduleEntryResponse(BaseModel):
    """
    Single appointment entry in the doctor's daily schedule view.

    Returned as part of the DoctorScheduleResponse list.
    """

    appointment_id: str = Field(..., description="Unique appointment identifier.")
    slot: str = Field(..., description="Appointment time slot in HH:MM format.")
    patient_name: str = Field(..., description="Full name of the patient.")
    reason: str = Field(..., description="Stated reason for the visit.")
    temperature: float = Field(..., description="Reported body temperature in Fahrenheit.")
    symptoms: List[str] = Field(..., description="List of reported symptoms.")
    is_cancelled: bool = Field(..., description="Whether the appointment was cancelled.")
    cancellation_reason: Optional[str] = Field(default=None, description="Reason for cancellation if applicable.")


class DoctorScheduleResponse(BaseModel):
    """
    Response schema for GET /doctor/schedule.

    Returns the full list of appointments for a given date,
    ordered chronologically by slot time.
    """

    date: str = Field(..., description="The queried schedule date in YYYY-MM-DD format.")
    is_unavailable: bool = Field(default=False, description="Whether the doctor is marked as unavailable on this date.")
    total_appointments: int = Field(
        ..., description="Total number of appointments on this date (including cancelled)."
    )
    schedule: List[ScheduleEntryResponse] = Field(
        ..., description="Ordered list of appointment details for the day."
    )


class DoctorUnavailabilityRequest(BaseModel):
    """Request schema for marking/unmarking a date as unavailable (off-day)."""

    date: str = Field(..., description="Target date in YYYY-MM-DD format.")
    is_unavailable: bool = Field(..., description="True to mark unavailable (off-day), False to mark available.")


class DoctorUnavailabilityResponse(BaseModel):
    """Response schema for doctor unavailability management."""

    date: str = Field(..., description="Target date in YYYY-MM-DD format.")
    is_unavailable: bool = Field(..., description="Current unavailability status for the date.")
    unavailable_dates: List[str] = Field(..., description="Full list of dates doctor is marked as unavailable.")
    cancelled_appointments_count: int = Field(0, description="Count of existing active appointments auto-cancelled.")
    message: str = Field(..., description="Confirmation message.")


class DoctorStatsResponse(BaseModel):
    """
    Response schema for GET /doctor/stats.

    Returns high-level clinic statistics for the doctor dashboard.
    """

    total_registered_patients: int = Field(
        ..., description="Total number of patients registered in the system."
    )
    todays_visit_count: int = Field(
        ..., description="Number of active (non-cancelled) appointments for today."
    )
    upcoming_visit_count: int = Field(
        ..., description="Number of active appointments scheduled for future dates."
    )
