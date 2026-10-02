"""
─────────────────────────────────────────────────────────────────────────────
File        : core/apis/schemas/discovery_schema.py
Purpose     : Pydantic response schemas for patient-facing discovery endpoints.

Endpoints served:
    GET /api/v1/hospitals
    GET /api/v1/hospitals/{hospital_id}/doctors
    GET /api/v1/hospitals/{hospital_id}/doctors/{doctor_id}/free-slots

These are read-only public/patient-facing routes. No request body schemas
are needed here — all inputs come from path or query parameters.

Used By:
    - core/apis/routes/appointment_routes.py
─────────────────────────────────────────────────────────────────────────────
"""

from typing import Dict, List

from pydantic import BaseModel, Field


class HospitalDiscoveryResponse(BaseModel):
    """
    Compact hospital entry returned by GET /api/v1/hospitals.

    Only exposes fields relevant to a patient choosing a hospital.
    Admin-only fields (owner_id, is_approved internals) are omitted.
    """

    hospital_id: str = Field(..., description="Unique identifier of the hospital.")
    name: str = Field(..., description="Display name of the hospital or clinic.")
    city: str = Field(..., description="City where the hospital is located.")
    address: str = Field(..., description="Full street address.")
    contact_number: str = Field(..., description="Primary contact phone number.")
    is_active: bool = Field(
        ..., description="Whether the hospital is currently accepting patients."
    )


class DoctorDiscoveryResponse(BaseModel):
    """
    Doctor profile entry returned by GET /api/v1/hospitals/{id}/doctors.

    Based on DoctorProfileModel with profile_id exposed as the canonical
    doctor identifier that patients must use in their booking request's
    doctor_id field.
    """

    profile_id: str = Field(
        ...,
        description=(
            "Unique identifier of the doctor's profile at this hospital. "
            "Use this value as doctor_id when booking an appointment."
        ),
    )
    user_id: str = Field(
        ..., description="String ObjectId of the doctor's user account."
    )
    name: str = Field(default="Doctor", description="Full name of the doctor.")
    email: str = Field(default="", description="Contact email of the doctor.")
    specialization: str = Field(..., description="Medical specialization.")
    consultation_fee: str = Field(..., description="Consultation fee per visit.")
    clinic_hours: Dict[str, str] = Field(
        ...,
        description="Working hours. Keys are session names ('morning', 'evening').",
    )
    languages_spoken: List[str] = Field(
        ..., description="Languages the doctor communicates in."
    )
    unavailable_dates: List[str] = Field(
        default_factory=list, description="Dates marked as unavailable by the doctor."
    )
    is_active: bool = Field(
        ..., description="Whether this doctor is currently accepting patients."
    )


class DoctorFreeSlotsResponse(BaseModel):
    """
    Available appointment slots for a specific doctor at a specific hospital on a given date.

    Returned by GET /api/v1/hospitals/{id}/doctors/{doctor_id}/free-slots.
    """

    hospital_id: str = Field(..., description="Hospital context for these slots.")
    doctor_id: str = Field(
        ...,
        description=(
            "The doctor_id (profile_id) whose availability is shown. "
            "Use this value in your booking request."
        ),
    )
    date: str = Field(..., description="Queried date in YYYY-MM-DD format.")
    available_slots: List[str] = Field(
        ..., description="Free time slots in HH:MM format."
    )
    total_available: int = Field(
        ..., description="Count of free slots for this doctor on this date."
    )
    is_unavailable: bool = Field(
        default=False, description="Whether the doctor is marked as unavailable on this date."
    )
