"""
─────────────────────────────────────────────────────────────────────────────
File        : core/apis/schemas/admin_schema.py
Purpose     : Pydantic request and response schemas for super-admin endpoints.

Responsibilities:
    - Validate admin request bodies (create hospital, create owner, set status)
    - Define structured response models for hospital and owner data
    - Provide Swagger-ready field descriptions and examples

Used By:
    - core/apis/routes/admin_routes.py
    - core/controllers/admin_controller.py
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# ─── Request Schemas ──────────────────────────────────────────────────────────


class CreateHospitalRequest(BaseModel):
    """
    Request body for POST /api/v1/admin/hospitals.

    Registers a new hospital tenant on the platform. The hospital starts
    as unapproved (is_approved=False) and must be explicitly approved
    before it goes live. owner_id is initially empty — it is set via a
    separate call to POST /api/v1/admin/hospitals/{id}/owner.
    """

    name: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Display name of the hospital or clinic.",
        examples=["CityCare Clinic"],
    )
    address: str = Field(
        ...,
        min_length=5,
        max_length=300,
        description="Full street address.",
        examples=["12, MG Road, Pune, Maharashtra – 411001"],
    )
    city: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="City where the hospital is located.",
        examples=["Pune"],
    )
    contact_number: str = Field(
        ...,
        min_length=7,
        max_length=20,
        description="Primary contact phone number.",
        examples=["+91-20-1234-5678"],
    )
    facilities: List[str] = Field(
        default_factory=list,
        max_length=50,
        description="Patient-visible facilities such as ICU, pharmacy, or diagnostics.",
    )
    services: List[str] = Field(
        default_factory=list,
        max_length=50,
        description="Patient-visible clinical services offered by the hospital.",
    )


class CreateHospitalOwnerRequest(BaseModel):
    """
    Request body for POST /api/v1/admin/hospitals/{hospital_id}/owner.

    Creates a HOSPITAL_OWNER user account and binds it to the given
    hospital. The caller must be SUPER_ADMIN. The new user receives
    role=hospital_owner and hospital_id set to the target hospital.
    """

    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Full name of the hospital owner.",
        examples=["Amit Desai"],
    )
    email: EmailStr = Field(
        ...,
        description="Email address for the owner's login account.",
        examples=["amit.desai@citycare.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Initial password for the owner account. Minimum 8 characters.",
        examples=["OwnerPass@2024"],
    )


class SetHospitalStatusRequest(BaseModel):
    """
    Request body for PATCH /api/v1/admin/hospitals/{hospital_id}/status.

    Allows SUPER_ADMIN to toggle the is_active and/or is_approved flags
    on a hospital. At least one field must be provided.
    """

    is_active: Optional[bool] = Field(
        default=None,
        description=(
            "Set to false to suspend the hospital (blocks all bookings). "
            "Set to true to reactivate."
        ),
    )
    is_approved: Optional[bool] = Field(
        default=None,
        description=(
            "Set to true to approve the hospital for live operation. "
            "Set to false to revoke approval."
        ),
    )


class UpdateHospitalServicesRequest(BaseModel):
    """Patient-visible facilities and clinical services for gateway surfaces."""

    facilities: List[str] = Field(default_factory=list, max_length=50)
    services: List[str] = Field(default_factory=list, max_length=50)


# ─── Response Schemas ─────────────────────────────────────────────────────────


class HospitalResponse(BaseModel):
    """
    Response body for hospital creation and status-change endpoints.

    Returns all persistent fields of the hospital document, plus
    a human-readable message describing the outcome of the operation.
    """

    hospital_id: str = Field(..., description="Unique identifier of the hospital.")
    name: str = Field(..., description="Display name of the hospital.")
    address: str = Field(..., description="Street address.")
    city: str = Field(..., description="City.")
    contact_number: str = Field(..., description="Primary contact phone number.")
    facilities: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    owner_id: str = Field(
        ...,
        description=(
            "String ObjectId of the HOSPITAL_OWNER user. "
            "Empty string until an owner is assigned."
        ),
    )
    is_active: bool = Field(..., description="Whether the hospital is currently active.")
    is_approved: bool = Field(
        ..., description="Whether the hospital has been approved by SUPER_ADMIN."
    )
    created_at: Optional[datetime] = Field(default=None, description="UTC timestamp of hospital registration.")
    message: str = Field(..., description="Human-readable outcome description.")


class HospitalOwnerResponse(BaseModel):
    """
    Response body for the create-hospital-owner endpoint.

    Returns the newly created owner user details and confirms the
    hospital binding. Does not expose password or hashed_password.
    """

    user_id: str = Field(..., description="Unique identifier of the new owner user.")
    name: str = Field(..., description="Full name of the owner.")
    email: str = Field(..., description="Login email address of the owner.")
    role: str = Field(..., description="Always 'hospital_owner'.")
    hospital_id: str = Field(
        ..., description="The hospital this owner is bound to."
    )
    message: str = Field(..., description="Human-readable outcome description.")


class HospitalListResponse(BaseModel):
    """
    Single entry in the GET /api/v1/admin/hospitals list response.
    """

    hospital_id: str
    name: str
    city: str
    owner_id: str
    is_active: bool
    is_approved: bool
    created_at: Optional[datetime] = None


class PlatformStatsResponse(BaseModel):
    """
    Response schema for GET /api/v1/admin/stats.

    Platform-wide high-level metrics across all hospital tenants.
    """

    total_hospitals: int = Field(..., description="Total hospitals registered.")
    active_hospitals: int = Field(..., description="Count of active hospitals.")
    approved_hospitals: int = Field(..., description="Count of approved hospitals.")
    total_doctors: int = Field(..., description="Total doctor profiles platform-wide.")
    total_patients: int = Field(..., description="Total patient user accounts.")
    total_appointments: int = Field(..., description="Total appointments booked across all hospitals.")
    active_appointments: int = Field(..., description="Total non-cancelled appointments.")


class HospitalStatsResponse(BaseModel):
    """
    Response schema for GET /api/v1/admin/hospitals/{id}/stats and GET /api/v1/hospital/stats.

    Specific high-level metrics for a single hospital tenant.
    """

    hospital_id: str = Field(..., description="Unique identifier of the hospital.")
    hospital_name: str = Field(..., description="Display name of the hospital.")
    total_doctors: int = Field(..., description="Total doctor profiles at this hospital.")
    active_doctors: int = Field(..., description="Active doctor profiles at this hospital.")
    total_appointments: int = Field(..., description="Total appointments booked at this hospital.")
    todays_appointments: int = Field(..., description="Today's active appointments.")
    upcoming_appointments: int = Field(..., description="Upcoming active appointments.")
    is_active: bool = Field(..., description="Whether the hospital is active.")
    is_approved: bool = Field(..., description="Whether the hospital is approved.")
