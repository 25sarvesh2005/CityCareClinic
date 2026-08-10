"""
─────────────────────────────────────────────────────────────────────────────
File        : core/controllers/hospital_controller.py
Purpose     : Business logic for hospital-owner doctor management operations.

Responsibilities:
    create_doctor()       — provision a DOCTOR user + DoctorProfileModel
    list_doctors()        — list all active/inactive doctors at the hospital
    set_doctor_status()   — activate or deactivate a doctor profile

Tenant Isolation Contract (most important rule in this file):
    hospital_id is ALWAYS taken from the `scope` dict (JWT payload) that
    is injected by get_hospital_scope(). It is NEVER read from the request
    body, path parameters, or any other client-controlled source.

    The schema (CreateDoctorRequest) reinforces this by not exposing a
    hospital_id field at all — but even if it did, this controller would
    still ignore it. The JWT is the single source of truth for tenant scope.

Write Order for create_doctor():
    1. Validate hospital exists and is_active (suspension check).
    2. Check email uniqueness.
    3. Create UserModel (role=doctor, hospital_id=from_jwt).
    4. Create DoctorProfileModel linked to user + hospital.
    If step 4 fails, delete the user created in step 3 to prevent orphans.

Used By:
    - core/apis/routes/hospital_routes.py
─────────────────────────────────────────────────────────────────────────────
"""

from bson import ObjectId
from typing import List

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError as PyMongoDuplicateKeyError

from common.auth import hash_password
from common.logger import get_logger
from core.apis.schemas.hospital_schema import (
    CreateDoctorRequest,
    DoctorListEntryResponse,
    DoctorProfileResponse,
    SetDoctorStatusRequest,
)
from core.constants import UserRole
from core.cruds.doctor_profile_crud import (
    create_doctor_profile,
    find_profile_by_id,
    find_profile_by_user_and_hospital,
    find_profiles_by_hospital,
    set_doctor_profile_active,
)
from core.cruds.hospital_crud import find_hospital_by_id
from core.cruds.user_crud import create_user, find_user_by_email
from core.database.database import get_engine
from core.models.doctor_profile_model import DoctorProfileModel
from core.models.user_model import UserModel

logger = get_logger(__name__)


class HospitalController:
    """Controller for hospital-owner doctor management operations."""

    async def create_doctor(
        self,
        request: CreateDoctorRequest,
        scope: dict,
    ) -> DoctorProfileResponse:
        """
        Provision a DOCTOR user account and create their DoctorProfileModel.

        hospital_id is extracted exclusively from the JWT scope — never from
        the request body, which intentionally has no hospital_id field.

        Args:
            request (CreateDoctorRequest): Validated request body.
            scope   (dict)               : JWT payload from get_hospital_scope().
                                           Must contain hospital_id and user_id.

        Returns:
            DoctorProfileResponse: The created user + profile details.

        Raises:
            HTTPException 403: Hospital is suspended (is_active=False).
            HTTPException 404: Hospital not found (should not happen if JWT is valid).
            HTTPException 409: Email already registered, or doctor already has
                               a profile at this hospital.
        """
        engine = get_engine()

        # ── Tenant scope comes from JWT, NEVER from request body ──────────────
        hospital_id: str = scope["hospital_id"]

        # 1. Validate hospital exists and is not suspended
        hospital = await find_hospital_by_id(engine, hospital_id)
        if not hospital:
            logger.error(
                "Hospital '%s' from JWT not found — token may be stale", hospital_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Your hospital was not found. Please contact the platform administrator.",
            )

        if not hospital.is_active:
            logger.warning(
                "Attempt to create doctor in suspended hospital '%s' by owner '%s'",
                hospital_id,
                scope.get("email"),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Your hospital is currently suspended. "
                    "Doctor accounts cannot be created while the hospital is inactive."
                ),
            )

        # 2. Check email uniqueness
        clean_email = request.email.strip().lower()
        existing_user = await find_user_by_email(engine, clean_email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        # 3. Create the UserModel for the doctor
        new_doctor_user = UserModel(
            name=request.name.strip(),
            email=clean_email,
            hashed_password=hash_password(request.password),
            role=UserRole.DOCTOR,
            hospital_id=hospital_id,   # from JWT — never from request body
            created_by=scope.get("user_id"),
        )

        try:
            saved_user = await create_user(engine, new_doctor_user)
        except PyMongoDuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        # 4. Create the DoctorProfileModel — if this fails, delete the user
        #    to avoid an orphaned user with role=doctor but no profile.
        new_profile = DoctorProfileModel(
            user_id=str(saved_user.id),
            hospital_id=hospital_id,   # from JWT — never from request body
            specialization=request.specialization.strip(),
            consultation_fee=request.consultation_fee.strip(),
            clinic_hours=request.clinic_hours or {
                "morning": "10:00 AM – 1:00 PM",
                "evening": "5:00 PM – 8:00 PM",
            },
            languages_spoken=request.languages_spoken or [],
            is_active=True,
        )

        try:
            saved_profile = await create_doctor_profile(engine, new_profile)
        except (PyMongoDuplicateKeyError, Exception) as exc:
            # Roll back the user to prevent orphan
            try:
                await engine.delete(saved_user)
                logger.warning(
                    "Rolled back doctor user '%s' after profile creation failure",
                    str(saved_user.id),
                )
            except Exception as rollback_exc:
                logger.error(
                    "Rollback failed for user '%s': %s",
                    str(saved_user.id),
                    str(rollback_exc),
                )
            if isinstance(exc, PyMongoDuplicateKeyError):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This doctor already has a profile at your hospital.",
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create doctor profile. The user account was rolled back.",
            )

        logger.info(
            "Doctor created — user_id: '%s', hospital_id: '%s', by owner: '%s'",
            str(saved_user.id),
            hospital_id,
            scope.get("email"),
        )

        return DoctorProfileResponse(
            profile_id=str(saved_profile.id),
            user_id=str(saved_user.id),
            hospital_id=hospital_id,
            name=saved_user.name,
            email=saved_user.email,
            specialization=saved_profile.specialization,
            consultation_fee=saved_profile.consultation_fee,
            clinic_hours=saved_profile.clinic_hours,
            languages_spoken=saved_profile.languages_spoken,
            is_active=saved_profile.is_active,
            created_at=saved_profile.created_at,
            message=(
                f"Doctor '{saved_user.name}' created and assigned to "
                f"'{hospital.name}' successfully."
            ),
        )

    async def list_doctors(self, scope: dict) -> List[DoctorListEntryResponse]:
        """
        List all doctor profiles at the calling owner's hospital.

        hospital_id taken from JWT scope — caller cannot request another
        hospital's doctor list by any means.

        Args:
            scope (dict): JWT payload from get_hospital_scope().

        Returns:
            List[DoctorListEntryResponse]: All doctor profiles for this hospital.
        """
        engine = get_engine()
        hospital_id: str = scope["hospital_id"]

        profiles = await find_profiles_by_hospital(engine, hospital_id)

        # Look up user documents for each doctor profile to populate name & email
        valid_user_ids = []
        for p in profiles:
            if p.user_id:
                try:
                    valid_user_ids.append(ObjectId(p.user_id))
                except Exception:
                    pass

        users = await engine.find(UserModel, UserModel.id.in_(valid_user_ids)) if valid_user_ids else []
        users_map = {str(u.id): u for u in users}

        return [
            DoctorListEntryResponse(
                profile_id=str(p.id),
                user_id=p.user_id,
                name=users_map[p.user_id].name if p.user_id in users_map else "Doctor",
                email=users_map[p.user_id].email if p.user_id in users_map else "",
                specialization=p.specialization,
                consultation_fee=p.consultation_fee,
                unavailable_dates=p.unavailable_dates or [],
                is_active=p.is_active,
                created_at=p.created_at,
            )
            for p in profiles
        ]

    async def set_doctor_status(
        self,
        profile_id: str,
        request: SetDoctorStatusRequest,
        scope: dict,
    ) -> DoctorProfileResponse:
        """
        Activate or deactivate a doctor profile, scoped to the caller's hospital.

        The profile lookup uses hospital_id from the JWT — an owner cannot
        modify profiles that belong to a different hospital.

        Args:
            profile_id (str)                 : String ObjectId of the profile.
            request    (SetDoctorStatusRequest): Contains is_active bool.
            scope      (dict)                : JWT payload from get_hospital_scope().

        Returns:
            DoctorProfileResponse: The updated profile.

        Raises:
            HTTPException 404: Profile not found within this hospital's scope.
        """
        engine = get_engine()
        hospital_id: str = scope["hospital_id"]

        profile = await find_profile_by_id(engine, hospital_id, profile_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found or does not belong to your hospital.",
            )

        updated_profile = await set_doctor_profile_active(
            engine, hospital_id, profile, request.is_active
        )

        # Look up the doctor user for the response name and email
        doctor_user = None
        if updated_profile.user_id:
            try:
                doctor_user = await engine.find_one(UserModel, UserModel.id == ObjectId(updated_profile.user_id))
            except Exception:
                pass

        action = "activated" if request.is_active else "deactivated"

        logger.info(
            "Doctor profile '%s' %s in hospital '%s' by owner '%s'",
            profile_id,
            action,
            hospital_id,
            scope.get("email"),
        )

        return DoctorProfileResponse(
            profile_id=str(updated_profile.id),
            user_id=updated_profile.user_id,
            hospital_id=hospital_id,
            name=doctor_user.name if doctor_user else "Doctor",
            email=doctor_user.email if doctor_user else "",
            specialization=updated_profile.specialization,
            consultation_fee=updated_profile.consultation_fee,
            clinic_hours=updated_profile.clinic_hours,
            languages_spoken=updated_profile.languages_spoken,
            is_active=updated_profile.is_active,
            created_at=updated_profile.created_at,
            message=f"Doctor profile has been {action} successfully.",
        )

