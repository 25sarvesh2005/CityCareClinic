"""
Pydantic schemas for chatbot API endpoints.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ChatRequestSchema(BaseModel):
    session_id: Optional[str] = Field(
        default=None, description="Optional existing session ID hex string."
    )
    message: str = Field(..., description="User's query or prompt for the assistant.")


class ChatMessageResponse(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    created_at: str


class ChatSessionResponse(BaseModel):
    session_id: str
    user_id: str
    hospital_id: str
    assistant_type: str = "schedule"
    title: str
    created_at: str


class ChatResponseSchema(BaseModel):
    session_id: str
    response: str
    messages: List[ChatMessageResponse] = Field(default=[])
