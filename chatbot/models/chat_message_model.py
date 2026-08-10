"""
ODMantic model representing an individual message within a chat session.
"""

from datetime import datetime, timezone
from typing import Optional
from odmantic import Field, Model
from pymongo import ASCENDING, IndexModel


class ChatMessageModel(Model):
    """
    Represents a single message in a chat history.
    role can be: 'user', 'assistant', 'system', 'tool'
    """

    session_id: str
    role: str
    content: str
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    model_config = {
        "collection": "chat_messages",
    }

    @classmethod
    def __indexes__(cls):
        return (
            IndexModel(
                [("session_id", ASCENDING), ("created_at", ASCENDING)],
                unique=False,
                name="idx_chat_session_created",
            ),
        )
