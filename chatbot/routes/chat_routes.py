"""
FastAPI router for Phase 6 Schedule-Assistant Chatbot.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from chatbot.controllers.chat_controller import ChatController
from chatbot.schemas.chat_schema import (
    ChatMessageResponse,
    ChatRequestSchema,
    ChatResponseSchema,
    ChatSessionResponse,
)
from common.tenant_scope import get_hospital_scope
from core.constants import UserRole

router = APIRouter(tags=["Schedule Chatbot"])

ALLOWED_CHAT_ROLES = {UserRole.PATIENT.value, UserRole.DOCTOR.value, UserRole.HOSPITAL_OWNER.value}
PATIENT_CHAT_ROLES = {UserRole.PATIENT.value}


def verify_chat_access(current_user: dict = Depends(get_hospital_scope)) -> dict:
    """Ensure authenticated user has a valid role for AI assistant access."""
    role = current_user.get("role")
    if role not in ALLOWED_CHAT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI assistant chatbot is accessible to Patients, Doctors, and Hospital Owners.",
        )
    return current_user


def verify_patient_prescription_access(
    current_user: dict = Depends(get_hospital_scope),
) -> dict:
    """Ensure only an authenticated patient can use prescription Q&A."""
    role = current_user.get("role")
    if role not in PATIENT_CHAT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Prescription assistant is accessible only to patients.",
        )
    return current_user


@router.post(
    "/v1/chat/schedule",
    response_model=ChatResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Interact with Schedule-Assistant Chatbot",
)
async def post_schedule_chat(
    request: ChatRequestSchema,
    scope: dict = Depends(verify_chat_access),
) -> ChatResponseSchema:
    """
    Send a natural language prompt to the schedule assistant.
    Powered by Gemini function calling with multi-turn session persistence.
    """
    return await ChatController().post_schedule_chat(
        current_user=scope, request=request
    )


@router.get(
    "/v1/chat/schedule/sessions",
    response_model=List[ChatSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="List my chatbot sessions",
)
async def list_chat_sessions(
    scope: dict = Depends(verify_chat_access),
) -> List[ChatSessionResponse]:
    """Retrieve all past chatbot sessions for the authenticated user."""
    return await ChatController().list_sessions(current_user=scope)


@router.get(
    "/v1/chat/schedule/sessions/{session_id}",
    response_model=List[ChatMessageResponse],
    status_code=status.HTTP_200_OK,
    summary="Get chatbot session message history",
)
async def get_session_messages(
    session_id: str,
    scope: dict = Depends(verify_chat_access),
) -> List[ChatMessageResponse]:
    """Retrieve full message history for a specific chat session."""
    return await ChatController().get_session_messages(
        session_id=session_id, current_user=scope
    )


@router.post(
    "/v1/chat/prescriptions",
    response_model=ChatResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Ask patient-scoped prescription questions",
)
async def post_prescription_chat(
    request: ChatRequestSchema,
    scope: dict = Depends(verify_patient_prescription_access),
) -> ChatResponseSchema:
    """
    Send a patient prescription question to the grounded prescription assistant.
    The patient_id always comes from the JWT, never from the request body.
    """
    return await ChatController().post_prescription_chat(
        current_user=scope, request=request
    )


@router.get(
    "/v1/chat/prescriptions/sessions",
    response_model=List[ChatSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="List my prescription chatbot sessions",
)
async def list_prescription_chat_sessions(
    scope: dict = Depends(verify_patient_prescription_access),
) -> List[ChatSessionResponse]:
    """Retrieve prescription assistant sessions for the authenticated patient."""
    return await ChatController().list_prescription_sessions(current_user=scope)


@router.get(
    "/v1/chat/prescriptions/sessions/{session_id}",
    response_model=List[ChatMessageResponse],
    status_code=status.HTTP_200_OK,
    summary="Get prescription chatbot session history",
)
async def get_prescription_session_messages(
    session_id: str,
    scope: dict = Depends(verify_patient_prescription_access),
) -> List[ChatMessageResponse]:
    """Retrieve messages for a prescription assistant session."""
    return await ChatController().get_prescription_session_messages(
        session_id=session_id, current_user=scope
    )
