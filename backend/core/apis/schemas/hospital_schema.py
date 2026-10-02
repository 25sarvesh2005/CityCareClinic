"""
─────────────────────────────────────────────────────────────────────────────
File        : core/apis/schemas/hospital_schema.py
Purpose     : Pydantic request and response schemas for hospital-owner endpoints.

Key design decision:
    CreateDoctorRequest intentionally has NO hospital_id field.
    This provides defence-in-depth: a client cannot inject a hospital_id
    into the request body because the field literally does not exist on
    the schema. The controller derives hospital_id exclusively from the
    JWT via the get_hospital_scope dependency.

Used By:
    - core/apis/routes/hospital_routes.py
    - core/controllers/hospital_controller.py
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# ─── Request Schemas ──────────────────────────────────────────────────────────


class CreateDoctorRequest(BaseModel):
    """
    Request body for POST /api/v1/hospital/doctors.

    Intentionally omits hospital_id — the caller's hospital is always
    derived from their JWT, never from the request body. Sending a
    hospital_id in the JSON will result in a 422 Unprocessable Entity
    (unknown field) if strict mode is enabled, or be silently ignored
    otherwise. Either way, it cannot affect the scope.
    """

    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Full name of the doctor (used for their login account).",
        examples=["Dr. Ananya Sharma"],
    )
    email: EmailStr = Field(
        ...,
        description="Email address for the doctor's login account.",
        examples=["dr.ananya@clinic.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Initial password for the doctor account. Minimum 8 characters.",
        examples=["DoctorPass@2024"],
    )
    specialization: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Medical specialization.",
        examples=["General Physician"],
    )
    consultation_fee: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Consultation fee string (e.g. 'Rs. 300').",
        examples=["Rs. 300"],
    )
    clinic_hours: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "Working hours dictionary. Defaults to morning 10:00–13:00 "
            "and evening 17:00–20:00 if not supplied."
        ),
        examples=[{"morning": "10:00 AM – 1:00 PM", "evening": "5:00 PM – 8:00 PM"}],
    )
    languages_spoken: Optional[List[str]] = Field(
        default=None,
        description="Languages the doctor speaks. Defaults to empty list if not supplied.",
        examples=[["English", "Hindi"]],
    )


class SetDoctorStatusRequest(BaseModel):
    """
    Request body for PATCH /api/v1/hospital/doctors/{id}/status.

    Allows the hospital owner to activate or deactivate a doctor profile.
    """

    is_active: bool = Field(
        ...,
        description=(
            "Set to false to deactivate the doctor (blocks new appointment bookings). "
            "Set to true to reactivate."
        ),
    )


# ─── Response Schemas ─────────────────────────────────────────────────────────


class DoctorProfileResponse(BaseModel):
    """
    Full doctor profile response, returned on create and status-change.
    """

    profile_id: str = Field(..., description="Unique identifier of the doctor profile.")
    user_id: str = Field(..., description="String ObjectId of the doctor's UserModel.")
    hospital_id: str = Field(..., description="Hospital this profile is scoped to.")
    name: str = Field(..., description="Full name of the doctor.")
    email: str = Field(..., description="Login email address of the doctor.")
    specialization: str = Field(..., description="Medical specialization.")
    consultation_fee: str = Field(..., description="Consultation fee.")
    clinic_hours: Dict[str, str] = Field(..., description="Working hours.")
    languages_spoken: List[str] = Field(..., description="Languages spoken.")
    is_active: bool = Field(..., description="Whether this doctor is accepting patients.")
    created_at: Optional[datetime] = Field(default=None, description="UTC timestamp of profile creation.")
    message: str = Field(..., description="Human-readable outcome description.")


class DoctorListEntryResponse(BaseModel):
    """
    Compact doctor entry for the GET /api/v1/hospital/doctors list.
    """

    profile_id: str
    user_id: str
    name: str
    email: str = ""
    specialization: str
    consultation_fee: str
    unavailable_dates: List[str] = Field(default_factory=list)
    is_active: bool
    created_at: Optional[datetime] = None

