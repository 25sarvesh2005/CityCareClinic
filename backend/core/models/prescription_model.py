"""
─────────────────────────────────────────────────────────────────────────────
File        : core/models/prescription_model.py
Purpose     : ODMantic document model representing a patient prescription.

Responsibilities:
    - Define schema for the 'prescriptions' collection in MongoDB
    - Link prescription records to appointments, doctors, and patients
    - Store diagnosis, medication details, advice, and Cloudinary PDF URLs
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from odmantic import Field, Model
from pymongo import ASCENDING, IndexModel


class PrescriptionModel(Model):
    """
    ODMantic model representing a patient prescription document.

    Maps to the 'prescriptions' collection in MongoDB.
    """

    hospital_id: str
    doctor_id: str
    doctor_name: str
    patient_id: str
    patient_name: str
    appointment_id: str
    date: str
    diagnosis: str
    medications: List[Dict[str, Any]] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None)
    follow_up_date: Optional[str] = Field(default=None)
    pdf_url: str = Field(default="")
    cloudinary_public_id: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "collection": "prescriptions",
    }

    @classmethod
    def __indexes__(cls):  # type: ignore[override]
        return (
            IndexModel(
                [("patient_id", ASCENDING), ("created_at", ASCENDING)],
                unique=False,
                name="idx_prescription_patient",
            ),
            IndexModel(
                [("appointment_id", ASCENDING)],
                unique=True,
                name="idx_prescription_appointment",
            ),
            IndexModel(
                [("hospital_id", ASCENDING), ("doctor_id", ASCENDING)],
                unique=False,
                name="idx_prescription_doctor",
            ),
        )
