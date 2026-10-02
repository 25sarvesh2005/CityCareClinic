"""FastAPI routes for Telegram webhook delivery and secure account pairing."""

import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status

from common.auth import get_current_user
from core.constants import UserRole
from core.database.database import get_engine
from telegram_bot.client import TelegramClient
from telegram_bot.cruds import create_link_code, mark_update_attempt
from telegram_bot.gateway import TelegramGateway, hash_link_code
from telegram_bot.schemas import TelegramLinkCodeResponse, TelegramWebhookResponse


router = APIRouter(prefix="/v1/telegram", tags=["Telegram Patient Gateway"])


def _verify_webhook_secret(received: str) -> None:
    configured = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram webhook is not configured.",
        )
    if not received or not hmac.compare_digest(received, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram webhook secret.",
        )


@router.get("/status", summary="Telegram gateway configuration status")
async def telegram_status() -> dict:
    """Expose readiness without revealing bot credentials."""
    return {
        "configured": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "webhook_secret_configured": bool(os.getenv("TELEGRAM_WEBHOOK_SECRET")),
        "mode": "webhook",
    }


@router.post(
    "/link-code",
    response_model=TelegramLinkCodeResponse,
    summary="Generate a one-time code to link an existing patient account",
)
async def generate_link_code(
    current_user: dict = Depends(get_current_user),
) -> TelegramLinkCodeResponse:
    """Issue a high-entropy, ten-minute pairing code to an authenticated patient."""
    if current_user.get("role") != UserRole.PATIENT.value:
        raise HTTPException(status_code=403, detail="Only patient accounts can link Telegram.")
    patient_id = current_user.get("user_id")
    if not patient_id:
        raise HTTPException(status_code=401, detail="Invalid patient identity.")
    raw_code = "MH-" + secrets.token_urlsafe(12)
    lifetime = 600
    await create_link_code(
        get_engine(),
        patient_id=patient_id,
        code_hash=hash_link_code(raw_code),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=lifetime),
    )
    return TelegramLinkCodeResponse(
        code=raw_code,
        expires_in_seconds=lifetime,
        instructions="Send /link CODE to the Medihub Telegram bot. The code works once and expires in 10 minutes.",
    )


@router.post(
    "/webhook",
    response_model=TelegramWebhookResponse,
    include_in_schema=False,
)
async def telegram_webhook(
    update: dict,
    telegram_secret: str = Header(default="", alias="X-Telegram-Bot-Api-Secret-Token"),
) -> TelegramWebhookResponse:
    """Verify, process, persist, and deliver one Telegram Bot API update."""
    _verify_webhook_secret(telegram_secret)
    gateway = TelegramGateway(get_engine())
    dispatch = await gateway.handle_update(update)
    if dispatch.in_progress:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram update is already being processed; retry shortly.",
        )
    if not dispatch.replies:
        await gateway.mark_delivered(dispatch.update_id)
        return TelegramWebhookResponse(ok=True, duplicate=dispatch.replayed)

    client = TelegramClient()
    try:
        await client.answer_callback(dispatch.callback_query_id)
        for reply in dispatch.replies:
            await client.send(reply)
        await gateway.mark_delivered(dispatch.update_id)
    except Exception:
        await mark_update_attempt(get_engine(), dispatch.update_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Telegram delivery failed; Telegram may retry this update.",
        )
    return TelegramWebhookResponse(ok=True, duplicate=dispatch.replayed)
