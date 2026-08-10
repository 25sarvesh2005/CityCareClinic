"""
─────────────────────────────────────────────────────────────────────────────
File        : core/apis/schemas/appointment_schema.py
Purpose     : Pydantic request and response schemas for appointment endpoints.

Responsibilities:
    - Validate the POST /book request body (Gate 2 structural validation)
    - Define structured response models for appointment data
    - Provide Swagger-ready field descriptions and examples

Used By:
    - core/apis/routes/appointment_router.py
    - core/controllers/appointment_controller.py

Gate 2 Validations (performed here at schema level):
    - reason       : minimum 10 characters
    - temperature  : must be between 95.0°F and 110.0°F
    - symptoms     : must contain at least one valid Symptom enum value
    - date / slot  : structural format only — business rules handled in controller
    - hospital_id  : required non-empty string (patient's chosen hospital)
    - doctor_id    : required non-empty string (patient's chosen doctor profile)

Notes:
    Date range validation (Gate 3) and slot existence check (Gate 4) are
    intentionally left to the controller — they require business context.
    Patient identity (patient_id) always comes from the JWT, never from
    the request body.
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from core.constants import (
    MAX_TEMPERATURE_FAHRENHEIT,
    MIN_REASON_LENGTH,
    MIN_TEMPERATURE_FAHRENHEIT,
    Symptom,
)


class BookAppointmentRequest(BaseModel):
    """
    Request body schema for POST /book.

    Applies Gate 2 structural and format validations inline.
    Business rules (date range, slot existence, duplicate check) are
    handled by the controller.

    Tenant scoping: hospital_id and doctor_id come from the request body
    because a patient (role=patient) has no hospital_id in their JWT— they
    are choosing which hospital/doctor to book with at request time.
    Patient identity (patient_id) ALWAYS comes from the JWT, never from here.
    """

    hospital_id: str = Field(
        ...,
        min_length=24,
        max_length=24,
        description=(
            "ObjectId of the hospital to book at. "
            "Obtain from GET /api/v1/hospitals."
        ),
        examples=["64b1f2c3d4e5f6a7b8c9d0e1"],
    )
    doctor_id: str = Field(
        ...,
        min_length=24,
        max_length=24,
        description=(
            "ObjectId of the doctor's profile at the chosen hospital. "
            "Obtain from GET /api/v1/hospitals/{id}/doctors (use profile_id)."
        ),
        examples=["64b1f2c3d4e5f6a7b8c9d0e2"],
    )
    date: str = Field(
        ...,
        description="Appointment date in YYYY-MM-DD format.",
        examples=["2025-08-15"],
    )
    slot: str = Field(
        ...,
        description="Desired time slot in HH:MM format (e.g. '10:00', '17:30').",
        examples=["10:00"],
    )
    reason: str = Field(
        ...,
        min_length=MIN_REASON_LENGTH,
        description=f"Reason for the visit. Minimum {MIN_REASON_LENGTH} characters.",
        examples=["I have been experiencing persistent fever and body pain for 3 days."],
    )
    temperature: float = Field(
        ...,
        ge=MIN_TEMPERATURE_FAHRENHEIT,
        le=MAX_TEMPERATURE_FAHRENHEIT,
        description=(
            f"Current body temperature in Fahrenheit. "
            f"Must be between {MIN_TEMPERATURE_FAHRENHEIT}°F and {MAX_TEMPERATURE_FAHRENHEIT}°F."
        ),
        examples=[99.5],
    )
    symptoms: List[Symptom] = Field(
        ...,
        min_length=1,
        description="List of reported symptoms. Must include at least one.",
        examples=[["fever", "bodyache"]],
    )

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, value: str) -> str:
        """
        Validate that the date string is a valid calendar date in YYYY-MM-DD format.

        Args:
            value (str): The raw date string from the request body.

        Returns:
            str: The validated date string.

        Raises:
            ValueError: If the string cannot be parsed as a valid date.
        """
        try:
            date.fromisoformat(value)
        except ValueError:
            raise ValueError("Date must be a valid calendar date in YYYY-MM-DD format.")
        return value


class AppointmentResponse(BaseModel):
    """
    Response schema for a single appointment record.

    Returned by POST /book and GET /my-appointments endpoints.
    """

    appointment_id: str = Field(..., description="Unique identifier of the appointment.")
    patient_name: str = Field(..., description="Full name of the patient.")
    date: str = Field(..., description="Appointment date in YYYY-MM-DD format.")
    slot: str = Field(..., description="Booked time slot in HH:MM format.")
    reason: str = Field(..., description="Stated reason for the visit.")
    temperature: float = Field(..., description="Reported body temperature in Fahrenheit.")
    symptoms: List[str] = Field(..., description="List of reported symptoms.")
    is_cancelled: bool = Field(..., description="True if this appointment has been cancelled.")
    cancellation_reason: Optional[str] = Field(default=None, description="Explanation if appointment was cancelled.")
    created_at: Optional[str] = Field(default="", description="UTC timestamp of when the booking was created.")
    message: str = Field(default="", description="Optional success message.")


class CancelResponse(BaseModel):
    """
    Response schema for DELETE /cancel/{appointment_id}.
    """

    appointment_id: str = Field(..., description="ID of the cancelled appointment.")
    message: str = Field(..., description="Confirmation message.")
