"""Transport-neutral schemas used by the Telegram gateway and Bot API client."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TelegramReply(BaseModel):
    """One outbound Telegram message and its optional inline keyboard."""

    chat_id: str
    text: str
    reply_markup: Optional[Dict[str, Any]] = None


class TelegramDispatch(BaseModel):
    """Durable result of processing one Telegram update."""

    update_id: int
    replies: List[TelegramReply] = Field(default_factory=list)
    replayed: bool = False
    callback_query_id: Optional[str] = None


class TelegramLinkCodeResponse(BaseModel):
    """One-time link code returned only to an authenticated patient."""

    code: str
    expires_in_seconds: int
    instructions: str


class TelegramWebhookResponse(BaseModel):
    """Acknowledgement returned to Telegram after an update is delivered."""

    ok: bool = True
    duplicate: bool = False


class TelegramHospital(BaseModel):
    """Patient-visible hospital details used only by the Telegram surface."""

    hospital_id: str
    name: str
    city: str
    address: str
    contact_number: str
    facilities: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    is_active: bool
