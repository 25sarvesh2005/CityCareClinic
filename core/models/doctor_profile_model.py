"""
─────────────────────────────────────────────────────────────────────────────
File        : core/models/doctor_profile_model.py
Purpose     : ODMantic document model for a doctor's clinic profile.

Responsibilities:
    - Separate clinical/professional attributes from authentication identity
    - Link a UserModel (role=doctor) to a specific hospital tenant
    - Store per-doctor clinic hours and consultation fee
    - Support activation (is_active) independent of the user account

Separation of Concerns:
    UserModel           → identity, login credentials, role
    DoctorProfileModel  → clinical profile, hospital affiliation, schedule

One doctor user can in theory have profiles at multiple hospitals; each
DoctorProfileModel document represents a single affiliation.

Used By:
    - core/cruds/doctor_profile_crud.py  (Phase 2)
    - core/controllers/doctor_controller.py  (Phase 2)

Indexes:
    - (user_id, hospital_id) : unique — one profile per doctor per hospital
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from odmantic import Field, Model
from pymongo import ASCENDING, IndexModel


class DoctorProfileModel(Model):
    """
    ODMantic model representing a doctor's profile at a specific hospital.

    Maps to the 'doctor_profiles' collection in MongoDB.

    Attributes:
        user_id           (str)       : String ObjectId of the associated UserModel (role=doctor).
        hospital_id       (str)       : String ObjectId of the HospitalModel this profile belongs to.
        specialization    (str)       : Medical specialization (e.g., 'General Physician').
        consultation_fee  (str)       : Fee string (e.g., 'Rs. 300').
        clinic_hours      (Dict)      : Dict describing working hours, e.g.
                                        {"morning": "10:00 AM – 1:00 PM",
                                         "evening": "5:00 PM – 8:00 PM"}
        languages_spoken  (List[str]) : Languages the doctor communicates in.
        is_active         (bool)      : Whether this doctor is currently accepting patients.
        created_at        (datetime)  : UTC timestamp of profile creation.
    """

    user_id: str
    hospital_id: str
    specialization: str
    consultation_fee: str
    clinic_hours: Dict[str, str] = Field(
        default={
            "morning": "10:00 AM – 1:00 PM",
            "evening": "5:00 PM – 8:00 PM",
        }
    )
    languages_spoken: List[str] = Field(default=[])
    unavailable_dates: List[str] = Field(default=[])
    is_active: bool = True
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "collection": "doctor_profiles",
    }

    @classmethod
    def __indexes__(cls):  # type: ignore[override]
        """
        Define MongoDB indexes for the doctor_profiles collection.

        Returns:
            tuple: A tuple of pymongo IndexModel objects.
        """
        return (
            # Compound unique: one profile per doctor per hospital
            IndexModel(
                [("user_id", ASCENDING), ("hospital_id", ASCENDING)],
                unique=True,
                name="unique_user_hospital",
            ),
            # Fast lookup of all doctors at a hospital
            IndexModel(
                [("hospital_id", ASCENDING)],
                unique=False,
                name="idx_hospital_id",
            ),
        )
