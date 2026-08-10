"""
ODMantic model representing a chatbot session.
"""

from datetime import datetime, timezone
from typing import Optional
from odmantic import Field, Model
from pymongo import ASCENDING, IndexModel


class ChatSessionModel(Model):
    """
    Represents a chat session between a user (doctor or hospital owner) and the chatbot.
    """

    user_id: str
    hospital_id: str
    title: Optional[str] = Field(default="Schedule Assistant Session")
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    model_config = {
        "collection": "chat_sessions",
    }

    @classmethod
    def __indexes__(cls):
        return (
            IndexModel(
                [("user_id", ASCENDING), ("created_at", ASCENDING)],
                unique=False,
                name="idx_chat_user_created",
            ),
        )
