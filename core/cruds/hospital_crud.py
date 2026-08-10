"""
─────────────────────────────────────────────────────────────────────────────
File        : core/cruds/hospital_crud.py
Purpose     : Database operations for the hospitals collection.

Responsibilities:
    - Persist new hospital documents
    - Retrieve hospitals by id or list all
    - Update is_active / is_approved status flags
    - Update owner_id after an owner account is created

Rules:
    - No business logic of any kind
    - No HTTPExceptions
    - No authentication or authorization
    - Only MongoDB operations via the ODMantic Engine

Used By:
    - core/controllers/admin_controller.py
─────────────────────────────────────────────────────────────────────────────
"""

from typing import List, Optional

from bson import ObjectId
from odmantic import AIOEngine

from common.logger import get_logger
from core.models.hospital_model import HospitalModel

logger = get_logger(__name__)


# ─── CRUD Functions ───────────────────────────────────────────────────────────


async def create_hospital(
    engine: AIOEngine, hospital: HospitalModel
) -> HospitalModel:
    """
    Persist a new HospitalModel document to the hospitals collection.

    Args:
        engine   (AIOEngine)    : The active ODMantic engine instance.
        hospital (HospitalModel): A fully constructed hospital document.

    Returns:
        HospitalModel: The saved document with its generated _id populated.

    Raises:
        Exception: Propagates any Motor or ODMantic write failure,
                   including DuplicateKeyError for the (name, city) index.
    """
    saved = await engine.save(hospital)
    logger.debug(
        "Hospital created — name: '%s', city: '%s'", hospital.name, hospital.city
    )
    return saved


async def find_hospital_by_id(
    engine: AIOEngine, hospital_id: str
) -> Optional[HospitalModel]:
    """
    Retrieve a single hospital document by its string ObjectId.

    Args:
        engine      (AIOEngine): The active ODMantic engine instance.
        hospital_id (str)      : String ObjectId of the hospital.

    Returns:
        Optional[HospitalModel]: The matching document, or None if not found
                                  or if the id string is malformed.
    """
    try:
        object_id = ObjectId(hospital_id)
    except Exception:
        logger.warning("Invalid hospital ObjectId format: %s", hospital_id)
        return None

    hospital = await engine.find_one(HospitalModel, HospitalModel.id == object_id)
    logger.debug(
        "Hospital lookup by id '%s' — found: %s", hospital_id, hospital is not None
    )
    return hospital


async def find_all_hospitals(engine: AIOEngine) -> List[HospitalModel]:
    """
    Retrieve all hospital documents, ordered by creation time ascending.

    Args:
        engine (AIOEngine): The active ODMantic engine instance.

    Returns:
        List[HospitalModel]: All hospital documents on the platform.
    """
    hospitals = await engine.find(
        HospitalModel, sort=HospitalModel.created_at
    )
    logger.debug("All hospitals fetched: %d records", len(hospitals))
    return list(hospitals)


async def set_hospital_active_status(
    engine: AIOEngine, hospital: HospitalModel, is_active: bool
) -> HospitalModel:
    """
    Update the is_active flag on a hospital document.

    Args:
        engine    (AIOEngine)    : The active ODMantic engine instance.
        hospital  (HospitalModel): The hospital document to update.
        is_active (bool)         : True to activate; False to suspend.

    Returns:
        HospitalModel: The updated document.
    """
    hospital.is_active = is_active
    updated = await engine.save(hospital)
    logger.debug(
        "Hospital '%s' is_active set to: %s", str(hospital.id), is_active
    )
    return updated


async def set_hospital_approved_status(
    engine: AIOEngine, hospital: HospitalModel, is_approved: bool
) -> HospitalModel:
    """
    Update the is_approved flag on a hospital document.

    Args:
        engine      (AIOEngine)    : The active ODMantic engine instance.
        hospital    (HospitalModel): The hospital document to update.
        is_approved (bool)         : True to approve; False to revoke approval.

    Returns:
        HospitalModel: The updated document.
    """
    hospital.is_approved = is_approved
    updated = await engine.save(hospital)
    logger.debug(
        "Hospital '%s' is_approved set to: %s", str(hospital.id), is_approved
    )
    return updated


async def set_hospital_owner_id(
    engine: AIOEngine, hospital: HospitalModel, owner_id: str
) -> HospitalModel:
    """
    Set the owner_id field on an existing hospital document.

    Called after a HOSPITAL_OWNER user is successfully created so the
    hospital document references its owner.

    Args:
        engine   (AIOEngine)    : The active ODMantic engine instance.
        hospital (HospitalModel): The hospital document to update.
        owner_id (str)          : String ObjectId of the new owner UserModel.

    Returns:
        HospitalModel: The updated document with owner_id populated.
    """
    hospital.owner_id = owner_id
    updated = await engine.save(hospital)
    logger.debug(
        "Hospital '%s' owner_id set to: '%s'", str(hospital.id), owner_id
    )
    return updated


async def count_total_hospitals(engine: AIOEngine) -> int:
    """Count total hospitals registered on the platform."""
    return await engine.count(HospitalModel)


async def count_active_hospitals(engine: AIOEngine) -> int:
    """Count hospitals where is_active is True."""
    return await engine.count(HospitalModel, HospitalModel.is_active == True)


async def count_approved_hospitals(engine: AIOEngine) -> int:
    """Count hospitals where is_approved is True."""
    return await engine.count(HospitalModel, HospitalModel.is_approved == True)

