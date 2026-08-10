"""
─────────────────────────────────────────────────────────────────────────────
File        : core/models/hospital_model.py
Purpose     : ODMantic document model representing a hospital tenant.

Responsibilities:
    - Define the schema for the 'hospitals' MongoDB collection
    - Uniquely identify each clinic/hospital on the platform
    - Track ownership (owner_id → UserModel._id of a HOSPITAL_OWNER)
    - Support activation / approval workflow managed by SUPER_ADMIN

Used By:
    - core/cruds/hospital_crud.py  (Phase 2)
    - core/controllers/hospital_controller.py  (Phase 2)

Indexes:
    - name + city : sparse unique — prevents duplicate clinic registrations
                    in the same city; allows same name in different cities

Notes:
    A hospital must have is_approved=True before patients can book or
    doctors can be scoped to it. is_active is the operator kill-switch.
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, timezone
from typing import Optional

from odmantic import Field, Model
from pymongo import ASCENDING, IndexModel


class HospitalModel(Model):
    """
    ODMantic model representing a hospital/clinic tenant document.

    Maps to the 'hospitals' collection in MongoDB.
    Each document represents one clinic registered on the platform.

    Attributes:
        name           (str)      : Display name of the hospital / clinic.
        address        (str)      : Street address.
        city           (str)      : City where the hospital is located.
        contact_number (str)      : Primary contact phone number.
        owner_id       (str)      : String ObjectId of the HOSPITAL_OWNER UserModel.
        is_active      (bool)     : Operator kill-switch; False suspends the hospital.
        is_approved    (bool)     : SUPER_ADMIN approval flag; False blocks all access.
        created_at     (datetime) : UTC timestamp of hospital registration.
    """

    name: str
    address: str
    city: str
    contact_number: str
    owner_id: str
    is_active: bool = True
    is_approved: bool = False  # Requires SUPER_ADMIN approval before going live
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "collection": "hospitals",
    }

    @classmethod
    def __indexes__(cls):  # type: ignore[override]
        """
        Define MongoDB indexes for the hospitals collection.

        Returns:
            tuple: A tuple of pymongo IndexModel objects.
        """
        return (
            # Composite index on (name, city) — prevents the same clinic name
            # from being registered twice in the same city
            IndexModel(
                [("name", ASCENDING), ("city", ASCENDING)],
                unique=True,
                name="unique_name_city",
            ),
            # Index on owner_id — fast lookup of all hospitals for a given owner
            IndexModel(
                [("owner_id", ASCENDING)],
                unique=False,
                name="idx_owner_id",
            ),
        )
