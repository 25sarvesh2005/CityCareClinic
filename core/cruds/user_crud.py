"""
─────────────────────────────────────────────────────────────────────────────
File        : core/cruds/user_crud.py
Purpose     : Database operations for the users collection.

Responsibilities:
    - Create new user documents in MongoDB
    - Retrieve user documents by email
    - Count total registered patients

Rules:
    - No business logic of any kind
    - No HTTPExceptions
    - No authentication or authorization
    - Only MongoDB operations via the ODMantic Engine

Used By:
    - core/controllers/auth_controller.py

Returns:
    - create_user()            → UserModel
    - find_user_by_email()     → Optional[UserModel]
    - count_all_patients()     → int

Raises:
    - Propagates raw exceptions to the controller for handling
─────────────────────────────────────────────────────────────────────────────
"""

from typing import Optional

from odmantic import AIOEngine

from common.logger import get_logger
from core.models.user_model import UserModel

# ─── Logger ───────────────────────────────────────────────────────────────────

logger = get_logger(__name__)


# ─── CRUD Functions ───────────────────────────────────────────────────────────


async def create_user(engine: AIOEngine, user: UserModel) -> UserModel:
    """
    Persist a new UserModel document to the users collection.

    Args:
        engine (AIOEngine): The active ODMantic engine instance.
        user   (UserModel): A fully constructed user document to save.

    Returns:
        UserModel: The saved document with its generated _id populated.

    Raises:
        Exception: Propagates any Motor or ODMantic write failure.
    """
    saved_user = await engine.save(user)
    logger.debug("User document created — email: %s, role: %s", user.email, user.role)
    return saved_user


async def find_user_by_email(engine: AIOEngine, email: str) -> Optional[UserModel]:
    """
    Retrieve a single user document matching the given email address.

    Args:
        engine (AIOEngine): The active ODMantic engine instance.
        email  (str)       : The email address to look up.

    Returns:
        Optional[UserModel]: The matching user document, or None if not found.

    Raises:
        Exception: Propagates any Motor or ODMantic read failure.
    """
    user = await engine.find_one(UserModel, UserModel.email == email)
    logger.debug("User lookup by email '%s' — found: %s", email, user is not None)
    return user


async def count_all_patients(engine: AIOEngine) -> int:
    """
    Count the total number of patient accounts in the users collection.

    Used by the doctor dashboard stats endpoint.

    Args:
        engine (AIOEngine): The active ODMantic engine instance.

    Returns:
        int: The total count of user documents with role 'patient'.

    Raises:
        Exception: Propagates any Motor or ODMantic read failure.
    """
    from core.constants import UserRole

    count = await engine.count(UserModel, UserModel.role == UserRole.PATIENT)
    logger.debug("Total registered patients count: %d", count)
    return count
