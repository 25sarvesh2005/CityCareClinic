"""
─────────────────────────────────────────────────────────────────────────────
File        : core/cruds/doctor_profile_crud.py
Purpose     : Database operations for the doctor_profiles collection.

Responsibilities:
    - Persist new doctor profile documents
    - Retrieve profiles scoped to a specific hospital tenant
    - Update is_active status on a profile

Tenant Scoping Rule:
    Every query function that reads or counts profiles takes hospital_id
    as a REQUIRED positional argument — it is structurally impossible to
    write an unscoped query from this module.

Rules:
    - No business logic of any kind
    - No HTTPExceptions
    - No authentication or authorization
    - Only MongoDB operations via the ODMantic Engine

Used By:
    - core/controllers/hospital_controller.py
─────────────────────────────────────────────────────────────────────────────
"""

from typing import List, Optional

from bson import ObjectId
from odmantic import AIOEngine
from pymongo.errors import DuplicateKeyError as PyMongoDuplicateKeyError

from common.logger import get_logger
from core.models.doctor_profile_model import DoctorProfileModel

logger = get_logger(__name__)


# ─── CRUD Functions ───────────────────────────────────────────────────────────


async def create_doctor_profile(
    engine: AIOEngine,
    profile: DoctorProfileModel,
) -> DoctorProfileModel:
    """
    Persist a new DoctorProfileModel document to the doctor_profiles collection.

    The unique compound index on (user_id, hospital_id) prevents a doctor
    from having duplicate profiles at the same hospital.

    Args:
        engine  (AIOEngine)         : The active ODMantic engine instance.
        profile (DoctorProfileModel): A fully constructed profile document.

    Returns:
        DoctorProfileModel: The saved document with its generated _id populated.

    Raises:
        PyMongoDuplicateKeyError: If this doctor already has a profile at the hospital.
        Exception: Propagates any other Motor or ODMantic write failure.
    """
    saved = await engine.save(profile)
    logger.debug(
        "Doctor profile created — user_id: '%s', hospital_id: '%s'",
        profile.user_id,
        profile.hospital_id,
    )
    return saved


async def find_profiles_by_hospital(
    engine: AIOEngine,
    hospital_id: str,
) -> List[DoctorProfileModel]:
    """
    Retrieve all doctor profiles belonging to a specific hospital tenant.

    Args:
        engine      (AIOEngine): The active ODMantic engine instance.
        hospital_id (str)      : Required tenant scope — never omit.

    Returns:
        List[DoctorProfileModel]: All profiles for the hospital, sorted by
                                   creation time ascending.
    """
    profiles = await engine.find(
        DoctorProfileModel,
        DoctorProfileModel.hospital_id == hospital_id,
        sort=DoctorProfileModel.created_at,
    )
    logger.debug(
        "Doctor profiles for hospital '%s' fetched: %d records",
        hospital_id,
        len(profiles),
    )
    return list(profiles)


async def find_profile_by_id(
    engine: AIOEngine,
    hospital_id: str,
    profile_id: str,
) -> Optional[DoctorProfileModel]:
    """
    Retrieve a single doctor profile by its ObjectId, scoped to a hospital.

    Scoping by hospital_id prevents cross-tenant profile access.

    Args:
        engine      (AIOEngine): The active ODMantic engine instance.
        hospital_id (str)      : Required tenant scope — never omit.
        profile_id  (str)      : String ObjectId of the profile document.

    Returns:
        Optional[DoctorProfileModel]: The matching profile, or None if not found
                                       or not belonging to this hospital.
    """
    try:
        object_id = ObjectId(profile_id)
    except Exception:
        logger.warning("Invalid profile ObjectId format: %s", profile_id)
        return None

    profile = await engine.find_one(
        DoctorProfileModel,
        (DoctorProfileModel.id == object_id)
        & (DoctorProfileModel.hospital_id == hospital_id),
    )
    logger.debug(
        "Profile lookup by id '%s' in hospital '%s' — found: %s",
        profile_id,
        hospital_id,
        profile is not None,
    )
    return profile


async def find_profile_by_user_and_hospital(
    engine: AIOEngine,
    hospital_id: str,
    user_id: str,
) -> Optional[DoctorProfileModel]:
    """
    Check whether a doctor user already has a profile at this hospital.

    Used before creating a new profile to give a clear duplicate error
    rather than surfacing a raw MongoDB DuplicateKeyError.

    Args:
        engine      (AIOEngine): The active ODMantic engine instance.
        hospital_id (str)      : Required tenant scope — never omit.
        user_id     (str)      : String ObjectId of the doctor UserModel.

    Returns:
        Optional[DoctorProfileModel]: Existing profile if found, else None.
    """
    profile = await engine.find_one(
        DoctorProfileModel,
        (DoctorProfileModel.hospital_id == hospital_id)
        & (DoctorProfileModel.user_id == user_id),
    )
    logger.debug(
        "Profile lookup for user '%s' in hospital '%s' — found: %s",
        user_id,
        hospital_id,
        profile is not None,
    )
    return profile


async def set_doctor_profile_active(
    engine: AIOEngine,
    hospital_id: str,
    profile: DoctorProfileModel,
    is_active: bool,
) -> DoctorProfileModel:
    """
    Update the is_active flag on a doctor profile, scoped to a hospital.

    Args:
        engine      (AIOEngine)         : The active ODMantic engine instance.
        hospital_id (str)               : Required tenant scope — never omit.
                                          Verified by the controller before call.
        profile     (DoctorProfileModel): The profile document to update.
        is_active   (bool)              : True to activate; False to deactivate.

    Returns:
        DoctorProfileModel: The updated profile document.
    """
    profile.is_active = is_active
    updated = await engine.save(profile)
    logger.debug(
        "Doctor profile '%s' in hospital '%s' is_active set to: %s",
        str(profile.id),
        hospital_id,
        is_active,
    )
    return updated


async def find_profile_by_user_id(
    engine: AIOEngine,
    user_id: str,
) -> Optional[DoctorProfileModel]:
    """
    Find a doctor profile by doctor user_id across hospitals (or first active profile).
    """
    profile = await engine.find_one(
        DoctorProfileModel,
        DoctorProfileModel.user_id == user_id,
    )
    return profile


async def update_doctor_unavailable_dates(
    engine: AIOEngine,
    profile: DoctorProfileModel,
    unavailable_dates: List[str],
) -> DoctorProfileModel:
    """
    Update the list of unavailable dates for a doctor profile.
    """
    profile.unavailable_dates = unavailable_dates
    updated = await engine.save(profile)
    logger.debug(
        "Doctor profile '%s' unavailable_dates updated: %s",
        str(profile.id),
        unavailable_dates,
    )
    return updated


async def count_all_doctor_profiles(engine: AIOEngine) -> int:
    """Count total doctor profiles across all hospitals."""
    return await engine.count(DoctorProfileModel)


async def count_hospital_doctors(engine: AIOEngine, hospital_id: str) -> int:
    """Count total doctor profiles for a specific hospital."""
    return await engine.count(
        DoctorProfileModel,
        DoctorProfileModel.hospital_id == hospital_id,
    )


async def count_hospital_active_doctors(engine: AIOEngine, hospital_id: str) -> int:
    """Count active doctor profiles for a specific hospital."""
    return await engine.count(
        DoctorProfileModel,
        (DoctorProfileModel.hospital_id == hospital_id)
        & (DoctorProfileModel.is_active == True),
    )

