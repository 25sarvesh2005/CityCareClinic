"""
─────────────────────────────────────────────────────────────────────────────
File        : core/controllers/admin_controller.py
Purpose     : Business logic for all super-admin hospital management operations.

Responsibilities:
    - create_hospital()        : Register a new hospital tenant
    - create_hospital_owner()  : Provision a HOSPITAL_OWNER user and bind it
    - set_hospital_status()    : Toggle is_active / is_approved on a hospital
    - list_hospitals()         : Retrieve all hospitals for the admin dashboard

Design Decisions:
    - create_hospital_owner writes in the order: create user first, then
      update hospital.owner_id. If the hospital update fails, the orphaned
      user is visible but harmless; the caller can retry and the duplicate-
      email check will surface it. This avoids a hospital with a corrupt
      owner_id reference.
    - All caller-identity claims (created_by) are taken from the JWT
      payload, never from the request body.
    - Hospital suspension (is_active=False) is enforced at the booking
      controller level in Phase 3; this controller only persists the flag.

Used By:
    - core/apis/routes/admin_routes.py
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import date
from typing import List

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError as PyMongoDuplicateKeyError

from common.auth import hash_password
from common.logger import get_logger
from core.apis.schemas.admin_schema import (
    CreateHospitalOwnerRequest,
    CreateHospitalRequest,
    HospitalListResponse,
    HospitalOwnerResponse,
    HospitalResponse,
    HospitalStatsResponse,
    PlatformStatsResponse,
    SetHospitalStatusRequest,
)
from core.constants import UserRole
from core.cruds.appointment_crud import (
    count_all_appointments,
    count_hospital_total_appointments,
    count_platform_active_appointments,
    count_today_appointments,
    count_upcoming_appointments,
)
from core.cruds.doctor_profile_crud import (
    count_all_doctor_profiles,
    count_hospital_active_doctors,
    count_hospital_doctors,
)
from core.cruds.hospital_crud import (
    count_active_hospitals,
    count_approved_hospitals,
    count_total_hospitals,
    create_hospital,
    find_all_hospitals,
    find_hospital_by_id,
    set_hospital_active_status,
    set_hospital_approved_status,
    set_hospital_owner_id,
)
from core.cruds.user_crud import count_all_patients, create_user, find_user_by_email
from core.database.database import get_engine
from core.models.hospital_model import HospitalModel
from core.models.user_model import UserModel

logger = get_logger(__name__)


class AdminController:
    """Controller for platform-level super-admin operations."""

    async def create_hospital(
        self,
        request: CreateHospitalRequest,
        admin_user: dict,
    ) -> HospitalResponse:
        """
        Register a new hospital tenant on the platform.

        The hospital is created with is_approved=False and owner_id=""
        (no owner yet). SUPER_ADMIN must approve it and assign an owner
        via subsequent calls.

        Args:
            request    (CreateHospitalRequest): Validated request body.
            admin_user (dict)                 : Decoded JWT of the calling SUPER_ADMIN.

        Returns:
            HospitalResponse: The persisted hospital document.

        Raises:
            HTTPException 409: A hospital with the same name already exists in that city.
            HTTPException 500: Any unexpected persistence failure.
        """
        engine = get_engine()

        new_hospital = HospitalModel(
            name=request.name.strip(),
            address=request.address.strip(),
            city=request.city.strip(),
            contact_number=request.contact_number.strip(),
            owner_id="",  # Populated when create_hospital_owner is called
            is_active=True,
            is_approved=False,
        )

        try:
            saved = await create_hospital(engine, new_hospital)
        except PyMongoDuplicateKeyError:
            logger.warning(
                "Duplicate hospital registration attempt — name: '%s', city: '%s'",
                request.name,
                request.city,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A hospital named '{request.name}' already exists in {request.city}."
                ),
            )

        logger.info(
            "Hospital created — id: '%s', name: '%s', by admin: '%s'",
            str(saved.id),
            saved.name,
            admin_user.get("email"),
        )

        return HospitalResponse(
            hospital_id=str(saved.id),
            name=saved.name,
            address=saved.address,
            city=saved.city,
            contact_number=saved.contact_number,
            owner_id=saved.owner_id,
            is_active=saved.is_active,
            is_approved=saved.is_approved,
            created_at=saved.created_at,
            message="Hospital registered successfully. Assign an owner and approve to go live.",
        )

    async def create_hospital_owner(
        self,
        hospital_id: str,
        request: CreateHospitalOwnerRequest,
        admin_user: dict,
    ) -> HospitalOwnerResponse:
        """
        Create a HOSPITAL_OWNER user account and bind it to the given hospital.

        Write order:
            1. Validate the hospital exists.
            2. Check email is not already registered.
            3. Create the UserModel (role=hospital_owner, hospital_id set).
            4. Patch hospital.owner_id to the new user's id.

        If step 4 fails, the user exists but the hospital has no owner reference
        — the admin can retry safely (step 2 will catch the duplicate email on
        retry and the admin can use a different email or investigate the DB).

        Args:
            hospital_id (str)                       : Target hospital ObjectId string.
            request     (CreateHospitalOwnerRequest): Validated request body.
            admin_user  (dict)                      : Decoded JWT of calling SUPER_ADMIN.

        Returns:
            HospitalOwnerResponse: The new owner user details.

        Raises:
            HTTPException 404: Hospital not found.
            HTTPException 409: Email already registered.
        """
        engine = get_engine()

        # 1. Validate hospital exists
        hospital = await find_hospital_by_id(engine, hospital_id)
        if not hospital:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hospital '{hospital_id}' not found.",
            )

        # 2. Check email uniqueness
        clean_email = request.email.strip().lower()
        existing_user = await find_user_by_email(engine, clean_email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        # 3. Create the owner user (hospital_id and created_by populated from context)
        new_owner = UserModel(
            name=request.name.strip(),
            email=clean_email,
            hashed_password=hash_password(request.password),
            role=UserRole.HOSPITAL_OWNER,
            hospital_id=hospital_id,
            created_by=admin_user.get("user_id"),
        )

        try:
            saved_owner = await create_user(engine, new_owner)
        except PyMongoDuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        # 4. Bind the hospital's owner_id to the newly created user
        await set_hospital_owner_id(engine, hospital, str(saved_owner.id))

        logger.info(
            "Hospital owner created — owner_id: '%s', hospital_id: '%s', by admin: '%s'",
            str(saved_owner.id),
            hospital_id,
            admin_user.get("email"),
        )

        return HospitalOwnerResponse(
            user_id=str(saved_owner.id),
            name=saved_owner.name,
            email=saved_owner.email,
            role=saved_owner.role.value,
            hospital_id=hospital_id,
            message=(
                f"Owner account created and bound to hospital '{hospital.name}'. "
                "The owner can now log in with their credentials."
            ),
        )

    async def set_hospital_status(
        self,
        hospital_id: str,
        request: SetHospitalStatusRequest,
        admin_user: dict,
    ) -> HospitalResponse:
        """
        Update the is_active and/or is_approved flags on a hospital.

        At least one flag must be supplied in the request. Both can be
        updated in a single call.

        Args:
            hospital_id (str)                   : Target hospital ObjectId string.
            request     (SetHospitalStatusRequest): Validated request body.
            admin_user  (dict)                  : Decoded JWT of calling SUPER_ADMIN.

        Returns:
            HospitalResponse: The updated hospital document.

        Raises:
            HTTPException 404: Hospital not found.
            HTTPException 422: Neither flag was provided in the request body.
        """
        engine = get_engine()

        if request.is_active is None and request.is_approved is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="At least one of 'is_active' or 'is_approved' must be provided.",
            )

        hospital = await find_hospital_by_id(engine, hospital_id)
        if not hospital:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hospital '{hospital_id}' not found.",
            )

        if request.is_active is not None:
            hospital = await set_hospital_active_status(engine, hospital, request.is_active)

        if request.is_approved is not None:
            hospital = await set_hospital_approved_status(engine, hospital, request.is_approved)

        logger.info(
            "Hospital '%s' status updated — is_active: %s, is_approved: %s — by admin: '%s'",
            hospital_id,
            hospital.is_active,
            hospital.is_approved,
            admin_user.get("email"),
        )

        action = (
            "suspended" if hospital.is_active is False
            else "approved" if hospital.is_approved is True
            else "updated"
        )

        return HospitalResponse(
            hospital_id=str(hospital.id),
            name=hospital.name,
            address=hospital.address,
            city=hospital.city,
            contact_number=hospital.contact_number,
            owner_id=hospital.owner_id,
            is_active=hospital.is_active,
            is_approved=hospital.is_approved,
            created_at=hospital.created_at,
            message=f"Hospital has been {action} successfully.",
        )

    async def list_hospitals(self) -> List[HospitalListResponse]:
        """
        Retrieve a summary list of all hospitals on the platform.

        Used by the super-admin dashboard to overview tenant status.

        Returns:
            List[HospitalListResponse]: All hospital records, sorted by creation time.
        """
        engine = get_engine()
        hospitals = await find_all_hospitals(engine)

        return [
            HospitalListResponse(
                hospital_id=str(h.id),
                name=h.name,
                city=h.city,
                owner_id=h.owner_id,
                is_active=h.is_active,
                is_approved=h.is_approved,
                created_at=h.created_at,
            )
            for h in hospitals
        ]

    async def get_platform_stats(self) -> PlatformStatsResponse:
        """
        Calculate platform-wide high-level metrics across all hospital tenants.
        """
        engine = get_engine()

        total_hospitals = await count_total_hospitals(engine)
        active_hospitals = await count_active_hospitals(engine)
        approved_hospitals = await count_approved_hospitals(engine)
        total_doctors = await count_all_doctor_profiles(engine)
        total_patients = await count_all_patients(engine)
        total_appointments = await count_all_appointments(engine)
        active_appointments = await count_platform_active_appointments(engine)

        return PlatformStatsResponse(
            total_hospitals=total_hospitals,
            active_hospitals=active_hospitals,
            approved_hospitals=approved_hospitals,
            total_doctors=total_doctors,
            total_patients=total_patients,
            total_appointments=total_appointments,
            active_appointments=active_appointments,
        )

    async def get_hospital_stats(self, hospital_id: str) -> HospitalStatsResponse:
        """
        Calculate metrics for a single hospital tenant.

        Written ONCE here and called by:
            - Super Admin route: GET /v1/admin/hospitals/{id}/stats (unscoped)
            - Hospital Owner route: GET /v1/hospital/stats (scoped via JWT)
        """
        engine = get_engine()
        hospital = await find_hospital_by_id(engine, hospital_id)
        if not hospital:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hospital '{hospital_id}' not found.",
            )

        today_date_str = date.today().isoformat()

        total_doctors = await count_hospital_doctors(engine, hospital_id)
        active_doctors = await count_hospital_active_doctors(engine, hospital_id)
        total_appointments = await count_hospital_total_appointments(engine, hospital_id)
        todays_appointments = await count_today_appointments(engine, hospital_id, today_date_str)
        upcoming_appointments = await count_upcoming_appointments(engine, hospital_id, today_date_str)

        return HospitalStatsResponse(
            hospital_id=str(hospital.id),
            hospital_name=hospital.name,
            total_doctors=total_doctors,
            active_doctors=active_doctors,
            total_appointments=total_appointments,
            todays_appointments=todays_appointments,
            upcoming_appointments=upcoming_appointments,
            is_active=hospital.is_active,
            is_approved=hospital.is_approved,
        )

