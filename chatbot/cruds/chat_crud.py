"""
Database operations for chatbot sessions and messages.
"""

from typing import List, Optional
from bson import ObjectId
from odmantic import AIOEngine

from chatbot.models.chat_message_model import ChatMessageModel
from chatbot.models.chat_session_model import ChatSessionModel
from common.logger import get_logger

logger = get_logger(__name__)


async def create_chat_session(
    engine: AIOEngine,
    user_id: str,
    hospital_id: str,
    title: Optional[str] = None,
    assistant_type: str = "schedule",
) -> ChatSessionModel:
    """
    Create and persist a new chat session.
    """
    session = ChatSessionModel(
        user_id=user_id,
        hospital_id=hospital_id,
        assistant_type=assistant_type,
        title=title or "Schedule Assistant Session",
    )
    saved = await engine.save(session)
    logger.debug("Chat session created: %s for user %s", str(saved.id), user_id)
    return saved


async def get_chat_session(
    engine: AIOEngine,
    session_id: str,
    user_id: str,
    assistant_type: Optional[str] = None,
) -> Optional[ChatSessionModel]:
    """
    Retrieve a chat session by ID, scoped to user_id for authorization.
    """
    try:
        obj_id = ObjectId(session_id)
    except Exception:
        return None

    query = (ChatSessionModel.id == obj_id) & (ChatSessionModel.user_id == user_id)
    if assistant_type:
        query = query & (ChatSessionModel.assistant_type == assistant_type)

    session = await engine.find_one(ChatSessionModel, query)
    return session


async def list_chat_sessions(
    engine: AIOEngine,
    user_id: str,
    assistant_type: Optional[str] = None,
) -> List[ChatSessionModel]:
    """
    List all chat sessions for a specific user ordered by created_at descending.
    """
    query = ChatSessionModel.user_id == user_id
    if assistant_type:
        query = query & (ChatSessionModel.assistant_type == assistant_type)

    sessions = await engine.find(ChatSessionModel, query, sort=ChatSessionModel.created_at.desc())
    return list(sessions)


async def create_chat_message(
    engine: AIOEngine, session_id: str, role: str, content: str
) -> ChatMessageModel:
    """
    Persist a new chat message for a given session.
    """
    msg = ChatMessageModel(
        session_id=session_id,
        role=role,
        content=content,
    )
    saved = await engine.save(msg)
    logger.debug(
        "Chat message created: %s (role: %s) in session %s",
        str(saved.id),
        role,
        session_id,
    )
    return saved


async def get_chat_messages(
    engine: AIOEngine, session_id: str
) -> List[ChatMessageModel]:
    """
    Retrieve all messages for a session ordered by created_at ascending.
    """
    messages = await engine.find(
        ChatMessageModel,
        ChatMessageModel.session_id == session_id,
        sort=ChatMessageModel.created_at.asc(),
    )
    return list(messages)
