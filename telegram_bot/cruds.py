"""MongoDB operations for Telegram gateway state and delivery persistence."""

from datetime import datetime
from typing import List, Optional

from odmantic import AIOEngine

from telegram_bot.models import (
    TelegramLinkCodeModel,
    TelegramMessageModel,
    TelegramSessionModel,
    TelegramUpdateModel,
    utc_now,
)


async def get_or_create_session(
    engine: AIOEngine,
    telegram_user_id: str,
    chat_id: str,
    username: Optional[str],
) -> TelegramSessionModel:
    """Resolve a platform-isolated session, creating it on first contact."""
    session = await engine.find_one(
        TelegramSessionModel,
        TelegramSessionModel.telegram_user_id == telegram_user_id,
    )
    if session:
        session.chat_id = chat_id
        session.username = username
        session.updated_at = utc_now()
        return await engine.save(session)
    return await engine.save(
        TelegramSessionModel(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            username=username,
        )
    )


async def save_session(
    engine: AIOEngine, session: TelegramSessionModel
) -> TelegramSessionModel:
    """Persist workflow state with a fresh modification timestamp."""
    session.updated_at = utc_now()
    return await engine.save(session)


async def add_message(
    engine: AIOEngine, session_id: str, role: str, content: str
) -> TelegramMessageModel:
    """Append one short-term memory item."""
    return await engine.save(
        TelegramMessageModel(session_id=session_id, role=role, content=content)
    )


async def recent_messages(
    engine: AIOEngine, session_id: str, limit: int = 12
) -> List[TelegramMessageModel]:
    """Return the newest bounded transcript in chronological order."""
    messages = await engine.find(
        TelegramMessageModel,
        TelegramMessageModel.session_id == session_id,
        sort=TelegramMessageModel.created_at.desc(),
        limit=limit,
    )
    return list(reversed(messages))


async def clear_messages(engine: AIOEngine, session_id: str) -> None:
    """Forget one Telegram conversation without unlinking its patient identity."""
    await engine.remove(
        TelegramMessageModel, TelegramMessageModel.session_id == session_id
    )


async def create_link_code(
    engine: AIOEngine, patient_id: str, code_hash: str, expires_at: datetime
) -> TelegramLinkCodeModel:
    """Replace prior codes and persist one short-lived link proof."""
    await engine.remove(
        TelegramLinkCodeModel, TelegramLinkCodeModel.patient_id == patient_id
    )
    return await engine.save(
        TelegramLinkCodeModel(
            patient_id=patient_id,
            code_hash=code_hash,
            expires_at=expires_at,
        )
    )


async def consume_link_code(
    engine: AIOEngine, code_hash: str
) -> Optional[TelegramLinkCodeModel]:
    """Atomically-enough consume a single-use code for the gateway workflow."""
    code = await engine.find_one(
        TelegramLinkCodeModel, TelegramLinkCodeModel.code_hash == code_hash
    )
    if not code:
        return None
    await engine.delete(code)
    return code


async def find_update(engine: AIOEngine, update_id: int) -> Optional[TelegramUpdateModel]:
    """Find a previously processed Telegram update."""
    return await engine.find_one(
        TelegramUpdateModel, TelegramUpdateModel.update_id == update_id
    )


async def save_update(
    engine: AIOEngine, update_id: int, chat_id: str, replies_json: str
) -> TelegramUpdateModel:
    """Persist replies before delivery so Telegram retries do not rerun effects."""
    return await engine.save(
        TelegramUpdateModel(
            update_id=update_id,
            chat_id=chat_id,
            replies_json=replies_json,
        )
    )


async def mark_update_delivered(engine: AIOEngine, update_id: int) -> None:
    """Complete one delivery-ledger record after all replies are accepted."""
    update = await find_update(engine, update_id)
    if update:
        update.delivered = True
        update.attempts += 1
        await engine.save(update)


async def mark_update_attempt(engine: AIOEngine, update_id: int) -> None:
    """Record a failed or interrupted outbound delivery attempt."""
    update = await find_update(engine, update_id)
    if update:
        update.attempts += 1
        await engine.save(update)

