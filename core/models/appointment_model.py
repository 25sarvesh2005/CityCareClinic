"""
─────────────────────────────────────────────────────────────────────────────
File        : core/models/appointment_model.py
Purpose     : ODMantic document model representing a clinic appointment.

Responsibilities:
    - Define the schema for the 'appointments' MongoDB collection
    - Enforce the unique (date + slot) constraint for Gate 4 protection
    - Support soft-delete via the is_cancelled flag
    - Store all clinical details for the doctor's schedule view

Used By:
    - core/cruds/appointment_crud.py
    - core/controllers/appointment_controller.py (via CRUD)
    - core/controllers/doctor_controller.py (via CRUD)

Indexes:
    - (date, slot) : unique — prevents double-booking at the database level
                     This is Gate 4: the database steel door.

Notes:
    Appointments are never hard-deleted. Cancellation sets is_cancelled=True,
    which frees the slot for rebooking while preserving the audit trail.
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, timezone
from typing import List, Optional

from odmantic import Field, Model
from pymongo import ASCENDING, IndexModel

from core.constants import Symptom


class AppointmentModel(Model):
    """
    ODMantic model representing a single appointment booking document.

    Maps to the 'appointments' collection in MongoDB.
    The unique compound index on (hospital_id, doctor_id, date, slot) enforces
    the no-double-booking rule at the database level, regardless of concurrent
    requests. hospital_id and doctor_id are required — it is intentionally
    impossible to create an appointment without tenant and doctor scope.

    Attributes:
        hospital_id         (str)          : String ObjectId of the HospitalModel — tenant scope.
        doctor_id           (str)          : String ObjectId of the UserModel (role=doctor).
        patient_id          (str)          : String ObjectId of the patient UserModel.
        patient_name        (str)          : Full name of the patient (denormalized for fast reads).
        date                (str)          : Appointment date in YYYY-MM-DD format.
        slot                (str)          : Appointment time slot in HH:MM format.
        reason              (str)          : Patient's stated reason for the visit.
        temperature         (float)        : Body temperature in degrees Fahrenheit.
        symptoms            (List[Symptom]): One or more reported symptoms.
        is_cancelled        (bool)         : Soft-delete flag. True if cancelled.
        cancellation_reason (Optional[str]): Detailed reason if appointment was cancelled.
        created_at          (datetime)     : UTC timestamp of when the booking was made.
    """

    hospital_id: str
    doctor_id: str
    patient_id: str
    patient_name: str
    date: str
    slot: str
    reason: str
    temperature: float
    symptoms: List[Symptom]
    is_cancelled: bool = False
    cancellation_reason: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "collection": "appointments",
    }

    @classmethod
    def __indexes__(cls):  # type: ignore[override]
        """
        Define MongoDB indexes for the appointments collection.

        The compound unique index on (hospital_id, doctor_id, date, slot) is Gate 4 —
        it prevents double-booking a specific doctor's slot at a specific hospital,
        even under simultaneous concurrent requests.

        Returns:
            tuple: A tuple of pymongo IndexModel objects.
        """
        return (
            # 4-column unique index — tenant + doctor + date + slot must be globally unique
            IndexModel(
                [
                    ("hospital_id", ASCENDING),
                    ("doctor_id", ASCENDING),
                    ("date", ASCENDING),
                    ("slot", ASCENDING),
                ],
                unique=True,
                name="unique_hospital_doctor_date_slot",
            ),
            # Supporting index for fast patient history queries
            IndexModel(
                [("patient_id", ASCENDING), ("created_at", ASCENDING)],
                unique=False,
                name="idx_patient_created",
            ),
        )
