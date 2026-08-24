"""
─────────────────────────────────────────────────────────────────────────────
File        : core/database/database.py
Purpose     : Singleton database connection manager for CityCare Clinic.
              Manages the Motor async client and the ODMantic Engine instance.

Responsibilities:
    - Initialize the Motor AsyncIOMotorClient on application startup
    - Provide the ODMantic Engine as a singleton via get_engine()
    - Ensure indexes defined on models are created in MongoDB
    - Cleanly close the connection on application shutdown

Flow:
    Application startup (lifespan)
        ↓
    connect_to_database() — creates client + engine
        ↓
    get_engine() — injected into CRUD functions
        ↓
    Application shutdown (lifespan)
        ↓
    close_database_connection() — closes Motor client

Used By:
    - main.py (lifespan events)
    - core/cruds/*.py (via get_engine())

Returns:
    get_engine() → AIOEngine — the active ODMantic async engine instance.

Raises:
    RuntimeError: If get_engine() is called before connect_to_database().

Example:
    from core.database.database import get_engine

    engine = get_engine()
    result = await engine.find_one(UserModel, UserModel.email == email)
─────────────────────────────────────────────────────────────────────────────
"""

import os
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine

from common.logger import get_logger

# ─── Logger ───────────────────────────────────────────────────────────────────

logger = get_logger(__name__)

# ─── Singleton State ──────────────────────────────────────────────────────────

_motor_client: Optional[AsyncIOMotorClient] = None
_odmantic_engine: Optional[AIOEngine] = None


# ─── Lifecycle Functions ──────────────────────────────────────────────────────


async def connect_to_database() -> None:
    """
    Initialize the Motor client and ODMantic Engine on application startup.

    Reads MONGO_URL and DB_NAME from environment variables.
    Sets the module-level singletons so get_engine() can serve them.

    Returns:
        None

    Raises:
        Exception: Propagates any Motor connection failure to the caller.
    """
    global _motor_client, _odmantic_engine

    mongo_url: str = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    database_name: str = os.getenv("DB_NAME", "citycare_clinic")

    logger.info("Connecting to MongoDB at: %s / %s", mongo_url, database_name)

    _motor_client = AsyncIOMotorClient(mongo_url)
    _odmantic_engine = AIOEngine(client=_motor_client, database=database_name)

    # Telegram identity and delivery guarantees depend on database-enforced
    # uniqueness/TTL indexes, not only application-level checks.
    from core.models.user_model import UserModel
    from telegram_bot.models import (
        TelegramLinkCodeModel,
        TelegramMessageModel,
        TelegramSessionModel,
        TelegramUpdateModel,
    )

    await _odmantic_engine.configure_database(
        [
            UserModel,
            TelegramSessionModel,
            TelegramMessageModel,
            TelegramLinkCodeModel,
            TelegramUpdateModel,
        ]
    )

    logger.info("Database connection established successfully")


async def close_database_connection() -> None:
    """
    Close the Motor client on application shutdown.

    Resets both singletons to None to allow clean re-initialization
    if the application is restarted within the same process.

    Returns:
        None
    """
    global _motor_client, _odmantic_engine

    if _motor_client is not None:
        _motor_client.close()
        logger.info("Database connection closed")

    _motor_client = None
    _odmantic_engine = None


# ─── Engine Accessor ──────────────────────────────────────────────────────────


def get_engine() -> AIOEngine:
    """
    Return the active ODMantic Engine singleton.

    Must only be called after connect_to_database() has been awaited.
    CRUD functions call this at the top of every database operation.

    Returns:
        AIOEngine: The active ODMantic async engine.

    Raises:
        RuntimeError: If called before connect_to_database().
    """
    if _odmantic_engine is None:
        raise RuntimeError(
            "Database engine is not initialized. "
            "Ensure connect_to_database() was called during application startup."
        )

    return _odmantic_engine
