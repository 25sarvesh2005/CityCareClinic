"""
Chatbot controller orchestrating session loading, history retrieval,
Gemini SDK turn completion, message persistence, and API response formatting.
"""

from typing import List
from fastapi import HTTPException, status
from starlette.concurrency import run_in_threadpool

from chatbot.cruds.chat_crud import (
    create_chat_message,
    create_chat_session,
    get_chat_messages,
    get_chat_session,
    list_chat_sessions,
)
from chatbot.gemini_client import run_chat_completion
from chatbot.prescription_assistant import answer_from_prescription_records
from chatbot.schemas.chat_schema import (
    ChatMessageResponse,
    ChatRequestSchema,
    ChatResponseSchema,
    ChatSessionResponse,
)
from common.logger import get_logger
from core.cruds.prescription_crud import find_prescriptions_by_patient
from core.database.database import get_engine

logger = get_logger(__name__)


class ChatController:
    """Orchestrates schedule chatbot interaction turns."""

    async def post_schedule_chat(
        self, current_user: dict, request: ChatRequestSchema
    ) -> ChatResponseSchema:
        """
        Process a user chat turn:
        1. Find or create ChatSessionModel for current_user.
        2. Retrieve existing message history.
        3. Persist user's new message.
        4. Invoke Gemini client with function calling tools.
        5. Persist assistant's text response.
        6. Return ChatResponseSchema.
        """
        engine = get_engine()
        user_id = current_user.get("user_id")
        hospital_id = current_user.get("hospital_id")

        if not user_id or not hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account must be bound to a hospital tenant.",
            )

        # 1. Resolve Session
        session_id = request.session_id
        if session_id:
            session = await get_chat_session(
                engine,
                session_id,
                user_id,
                assistant_type="schedule",
            )
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Chat session '{session_id}' not found.",
                )
        else:
            session_title = f"Schedule Assistant ({request.message[:25]}...)"
            session = await create_chat_session(
                engine,
                user_id=user_id,
                hospital_id=hospital_id,
                title=session_title,
                assistant_type="schedule",
            )

        session_id_str = str(session.id)

        # 2. Get history before adding user message
        existing_msgs = await get_chat_messages(engine, session_id_str)
        history_list = [
            {"role": m.role, "content": m.content}
            for m in existing_msgs
            if m.role in ("user", "assistant")
        ]

        # 3. Persist user's message
        await create_chat_message(
            engine, session_id=session_id_str, role="user", content=request.message
        )

        # 4. Invoke Gemini AI assistant
        assistant_reply = await run_chat_completion(
            engine=engine,
            current_user=current_user,
            messages_history=history_list,
            user_prompt=request.message,
        )

        # 5. Persist assistant reply
        await create_chat_message(
            engine, session_id=session_id_str, role="assistant", content=assistant_reply
        )

        # 6. Fetch updated message list to return
        updated_msgs = await get_chat_messages(engine, session_id_str)
        formatted_messages = [
            ChatMessageResponse(
                message_id=str(m.id),
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat() if m.created_at else "",
            )
            for m in updated_msgs
        ]

        return ChatResponseSchema(
            session_id=session_id_str,
            response=assistant_reply,
            messages=formatted_messages,
        )

    async def list_sessions(self, current_user: dict) -> List[ChatSessionResponse]:
        """List chat sessions for authenticated user."""
        engine = get_engine()
        user_id = current_user.get("user_id")
        sessions = await list_chat_sessions(engine, user_id, assistant_type="schedule")
        return [
            ChatSessionResponse(
                session_id=str(s.id),
                user_id=s.user_id,
                hospital_id=s.hospital_id,
                assistant_type=s.assistant_type,
                title=s.title or "Schedule Session",
                created_at=s.created_at.isoformat() if s.created_at else "",
            )
            for s in sessions
        ]

    async def get_session_messages(
        self, session_id: str, current_user: dict
    ) -> List[ChatMessageResponse]:
        """Get messages for a specific session ID."""
        engine = get_engine()
        user_id = current_user.get("user_id")

        session = await get_chat_session(
            engine,
            session_id,
            user_id,
            assistant_type="schedule",
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found.",
            )

        messages = await get_chat_messages(engine, session_id)
        return [
            ChatMessageResponse(
                message_id=str(m.id),
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat() if m.created_at else "",
            )
            for m in messages
        ]

    async def post_prescription_chat(
        self, current_user: dict, request: ChatRequestSchema
    ) -> ChatResponseSchema:
        """Process a patient prescription Q&A turn with strict patient scoping."""
        engine = get_engine()
        user_id = current_user.get("user_id")

        if current_user.get("role") != "patient" or not user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Prescription assistant is available only to authenticated patients.",
            )

        session_id = request.session_id
        if session_id:
            session = await get_chat_session(
                engine,
                session_id,
                user_id,
                assistant_type="prescription",
            )
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Prescription chat session '{session_id}' not found.",
                )
        else:
            session_title = f"Prescription Assistant ({request.message[:25]}...)"
            session = await create_chat_session(
                engine,
                user_id=user_id,
                hospital_id=current_user.get("hospital_id") or "patient-self",
                title=session_title,
                assistant_type="prescription",
            )

        session_id_str = str(session.id)
        await create_chat_message(
            engine,
            session_id=session_id_str,
            role="user",
            content=request.message,
        )

        prescriptions = await find_prescriptions_by_patient(engine, user_id)
        result = await run_in_threadpool(
            answer_from_prescription_records,
            request.message,
            prescriptions,
        )
        assistant_reply = result.answer

        await create_chat_message(
            engine,
            session_id=session_id_str,
            role="assistant",
            content=assistant_reply,
        )

        updated_msgs = await get_chat_messages(engine, session_id_str)
        formatted_messages = [
            ChatMessageResponse(
                message_id=str(m.id),
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat() if m.created_at else "",
            )
            for m in updated_msgs
        ]

        return ChatResponseSchema(
            session_id=session_id_str,
            response=assistant_reply,
            messages=formatted_messages,
        )

    async def list_prescription_sessions(
        self, current_user: dict
    ) -> List[ChatSessionResponse]:
        """List prescription assistant sessions for one authenticated patient."""
        engine = get_engine()
        user_id = current_user.get("user_id")
        sessions = await list_chat_sessions(engine, user_id, assistant_type="prescription")
        return [
            ChatSessionResponse(
                session_id=str(s.id),
                user_id=s.user_id,
                hospital_id=s.hospital_id,
                assistant_type=s.assistant_type,
                title=s.title or "Prescription Session",
                created_at=s.created_at.isoformat() if s.created_at else "",
            )
            for s in sessions
        ]

    async def get_prescription_session_messages(
        self, session_id: str, current_user: dict
    ) -> List[ChatMessageResponse]:
        """Get messages for one patient prescription assistant session."""
        engine = get_engine()
        user_id = current_user.get("user_id")

        session = await get_chat_session(
            engine,
            session_id,
            user_id,
            assistant_type="prescription",
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prescription session '{session_id}' not found.",
            )

        messages = await get_chat_messages(engine, session_id)
        return [
            ChatMessageResponse(
                message_id=str(m.id),
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat() if m.created_at else "",
            )
            for m in messages
        ]
