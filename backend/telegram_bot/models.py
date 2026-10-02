"""Persistent Telegram identity, workflow, transcript, and delivery models."""

from datetime import datetime, timezone
from typing import List, Optional

from odmantic import Field, Model
from pymongo import ASCENDING, IndexModel


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class TelegramSessionModel(Model):
    """One isolated workflow session per Telegram user."""

    telegram_user_id: str
    chat_id: str
    username: Optional[str] = None
    patient_id: Optional[str] = None
    state: str = "idle"
    selected_hospital_id: Optional[str] = None
    selected_doctor_id: Optional[str] = None
    last_specialization_query: Optional[str] = None
    booking_date: Optional[str] = None
    booking_slot: Optional[str] = None
    booking_reason: Optional[str] = None
    booking_temperature: Optional[float] = None
    booking_symptoms: List[str] = Field(default=[])
    pending_name: Optional[str] = None
    pending_email: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    model_config = {"collection": "telegram_sessions"}

    @classmethod
    def __indexes__(cls):  # type: ignore[override]
        return (
            IndexModel(
                [("telegram_user_id", ASCENDING)],
                unique=True,
                name="unique_telegram_session_user",
            ),
        )


class TelegramMessageModel(Model):
    """Bounded conversation transcript used as short-term agent memory."""

    session_id: str
    role: str
    content: str
    created_at: datetime = Field(default_factory=utc_now)

    model_config = {"collection": "telegram_messages"}

    @classmethod
    def __indexes__(cls):  # type: ignore[override]
        return (
            IndexModel(
                [("session_id", ASCENDING), ("created_at", ASCENDING)],
                name="idx_telegram_message_session_created",
            ),
            IndexModel(
                [("created_at", ASCENDING)],
                expireAfterSeconds=30 * 24 * 60 * 60,
                name="ttl_telegram_messages_30_days",
            ),
        )


class TelegramLinkCodeModel(Model):
    """Short-lived, one-time proof used to link an existing patient account."""

    patient_id: str
    code_hash: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=utc_now)

    model_config = {"collection": "telegram_link_codes"}

    @classmethod
    def __indexes__(cls):  # type: ignore[override]
        return (
            IndexModel([("code_hash", ASCENDING)], unique=True, name="unique_link_code"),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_link_code"),
        )


class TelegramUpdateModel(Model):
    """Durable replay ledger for Telegram's at-least-once webhook delivery."""

    update_id: int
    chat_id: str
    replies_json: str = "[]"
    status: str = "pending"
    delivered: bool = False
    attempts: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    model_config = {"collection": "telegram_updates"}

    @classmethod
    def __indexes__(cls):  # type: ignore[override]
        return (
            IndexModel([("update_id", ASCENDING)], unique=True, name="unique_telegram_update"),
            IndexModel(
                [("created_at", ASCENDING)],
                expireAfterSeconds=7 * 24 * 60 * 60,
                name="ttl_telegram_updates_7_days",
            ),
        )
