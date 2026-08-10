"""
─────────────────────────────────────────────────────────────────────────────
File        : core/constants.py
Purpose     : Single source of truth for all enums, clinic configuration,
              and slot utility functions.

Replaces:
    - core/enums/role_enum.py
    - core/enums/symptom_enum.py
    - core/constants/clinic_constants.py
    - core/utils/slot_utils.py
─────────────────────────────────────────────────────────────────────────────
"""

from enum import Enum
from typing import Final, List

# ─── Enums ────────────────────────────────────────────────────────────────────


class UserRole(str, Enum):
    """
    Enumeration of all valid user roles in the CityCare Clinic system.

    Inheriting from str ensures that FastAPI serializes the role as a
    plain string in JSON responses rather than as an enum object.

    Values:
        PATIENT        : Standard registered user who books appointments.
        DOCTOR         : Privileged user with access to the doctor dashboard.
        HOSPITAL_OWNER : Owns and administers a hospital tenant.
        SUPER_ADMIN    : Platform-level administrator with cross-tenant access.
    """

    PATIENT = "patient"
    DOCTOR = "doctor"
    HOSPITAL_OWNER = "hospital_owner"
    SUPER_ADMIN = "super_admin"


class Symptom(str, Enum):
    """
    Enumeration of all symptoms the clinic accepts during booking.

    Patients must select at least one symptom from this list.
    Inheriting from str ensures clean JSON serialization.

    Values:
        FEVER    : Elevated body temperature.
        COUGH    : Persistent cough.
        COLD     : Runny nose or congestion.
        BODYACHE : General body or muscle pain.
        HEADACHE : Head pain.
        OTHER    : Any symptom not listed above.
    """

    FEVER = "fever"
    COUGH = "cough"
    COLD = "cold"
    BODYACHE = "bodyache"
    HEADACHE = "headache"
    OTHER = "other"


# ─── Booking Window ───────────────────────────────────────────────────────────

MAX_BOOKING_DAYS: Final[int] = 7
"""Maximum number of days ahead a patient can book an appointment."""

MAX_PATIENTS_PER_SLOT: Final[int] = 1
"""Maximum number of patients allowed per consultation slot."""

# ─── Appointment Slot Validation ──────────────────────────────────────────────

MIN_REASON_LENGTH: Final[int] = 10
"""Minimum number of characters required in the appointment reason field."""

MIN_TEMPERATURE_FAHRENHEIT: Final[float] = 95.0
"""Minimum acceptable body temperature in degrees Fahrenheit."""

MAX_TEMPERATURE_FAHRENHEIT: Final[float] = 110.0
"""Maximum acceptable body temperature in degrees Fahrenheit."""

# ─── Clinic Slots ─────────────────────────────────────────────────────────────

CLINIC_SLOTS: Final[list[str]] = [
    # Morning session — 10:00 to 13:00
    "10:00",
    "10:30",
    "11:00",
    "11:30",
    "12:00",
    "12:30",
    # Evening session — 17:00 to 20:00
    "17:00",
    "17:30",
    "18:00",
    "18:30",
    "19:00",
    "19:30",
]
"""
Complete list of all 12 fixed appointment slots for each clinic day.

Morning  : 10:00, 10:30, 11:00, 11:30, 12:00, 12:30
Evening  : 17:00, 17:30, 18:00, 18:30, 19:00, 19:30
"""

# ─── Doctor & Clinic Information ──────────────────────────────────────────────

DOCTOR_INFO: Final[dict] = {
    "doctor_name": "Dr. Meera Kulkarni",
    "specialization": "General Physician",
    "clinic_name": "CityCare Clinic",
    "consultation_fee": "Rs. 300",
    "morning_hours": "10:00 AM – 1:00 PM",
    "evening_hours": "5:00 PM – 8:00 PM",
    "slot_duration_minutes": 30,
    "total_slots_per_day": len(CLINIC_SLOTS),
    "max_patients_per_slot": MAX_PATIENTS_PER_SLOT,
    "languages_spoken": ["English", "Hindi", "Marathi"],
    "address": "12, MG Road, Pune, Maharashtra – 411001",
    "phone": "+91-20-1234-5678",
}
"""
Static profile information for the clinic's doctor.
Returned by the GET /doctor-info public endpoint.
"""

# ─── Slot Utility Functions ───────────────────────────────────────────────────


def generate_all_slots() -> List[str]:
    """
    Return the complete list of all 12 clinic appointment slots.

    Returns:
        List[str]: All 12 slot strings in HH:MM format, in chronological order.
    """
    return list(CLINIC_SLOTS)


def calculate_free_slots(booked_slots: List[str]) -> List[str]:
    """
    Calculate the list of available slots by removing booked slots.

    Args:
        booked_slots (List[str]): Time slots already booked for the date.

    Returns:
        List[str]: Remaining available slots in HH:MM format.

    Example:
        booked  = ["10:00", "17:30"]
        result  = all 12 slots minus ["10:00", "17:30"]
                → 10 free slots
    """
    booked_set = set(booked_slots)
    return [slot for slot in CLINIC_SLOTS if slot not in booked_set]


def is_valid_slot(slot: str) -> bool:
    """
    Check whether a given slot string is part of the clinic's menu.

    Args:
        slot (str): A time slot string in HH:MM format.

    Returns:
        bool: True if the slot is on the clinic menu, False otherwise.
    """
    return slot in CLINIC_SLOTS
