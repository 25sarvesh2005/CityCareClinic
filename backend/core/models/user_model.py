"""
─────────────────────────────────────────────────────────────────────────────
File        : core/models/user_model.py
Purpose     : ODMantic document model representing a registered clinic user.

Responsibilities:
    - Define the schema for the 'users' MongoDB collection
    - Enforce unique constraint on email address
    - Store hashed passwords (never plain-text)
    - Track user role for RBAC enforcement
    - Capture creation timestamp in UTC

Used By:
    - core/cruds/user_crud.py
    - core/controllers/auth_controller.py (via CRUD)

Indexes:
    - email  : unique — prevents duplicate registrations

Notes:
    The model never stores plain-text passwords. The hashed_password field
    must always receive a bcrypt hash from common/auth.py.
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, timezone
from typing import Optional

from odmantic import Field, Model
from pymongo import ASCENDING, IndexModel

from core.constants import UserRole


class UserModel(Model):
    """
    ODMantic model representing a CityCare Clinic user document.

    Maps to the 'users' collection in MongoDB.
    Every document represents a patient, doctor, hospital owner, or platform admin.

    Attributes:
        name            (str)           : Full name of the user.
        email           (str)           : Unique email address used for login.
        hashed_password (str)           : bcrypt hash of the user's password.
        role            (UserRole)      : 'patient', 'doctor', 'hospital_owner', or 'super_admin'.
        hospital_id     (Optional[str]) : String ObjectId of the associated HospitalModel.
                                          Populated for DOCTOR and HOSPITAL_OWNER roles.
                                          None for PATIENT and SUPER_ADMIN.
        created_by      (Optional[str]) : String ObjectId of the UserModel who provisioned
                                          this account. Used for audit trails when a
                                          SUPER_ADMIN or HOSPITAL_OWNER creates accounts.
        created_at      (datetime)      : UTC timestamp of account creation.
    """

    name: str
    email: str
    hashed_password: str
    role: UserRole = UserRole.PATIENT
    hospital_id: Optional[str] = None
    created_by: Optional[str] = Field(default=None)
    phone_number: Optional[str] = Field(default=None)
    telegram_user_id: Optional[str] = Field(default=None)
    registration_source: str = Field(default="web")
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "collection": "users",
    }

    @classmethod
    def __indexes__(cls):  # type: ignore[override]
        """
        Define MongoDB indexes for the users collection.

        Returns:
            tuple: A tuple of pymongo IndexModel objects.
        """
        return (
            # Unique index on email — prevents duplicate registrations
            IndexModel([("email", ASCENDING)], unique=True, name="unique_email"),
            IndexModel(
                [("telegram_user_id", ASCENDING)],
                unique=True,
                name="unique_telegram_user_id",
                partialFilterExpression={"telegram_user_id": {"$type": "string"}},
            ),
        )
