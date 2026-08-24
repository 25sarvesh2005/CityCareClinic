"""Local-development long-polling runner for the Medihub Telegram gateway."""

import asyncio
import os

import httpx

from core.database.database import close_database_connection, connect_to_database, get_engine
from telegram_bot.client import TelegramClient
from telegram_bot.cruds import mark_update_attempt
from telegram_bot.gateway import TelegramGateway


async def run() -> None:
    """Poll Telegram sequentially and dispatch through the same persistent gateway."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
    api_root = os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org").rstrip("/")
    updates_url = f"{api_root}/bot{token}/getUpdates"
    await connect_to_database()
    gateway = TelegramGateway(get_engine())
    client = TelegramClient(token=token, base_url=api_root)
    offset = 0
    try:
        async with httpx.AsyncClient(timeout=40) as http:
            while True:
                response = await http.get(
                    updates_url,
                    params={"timeout": 30, "offset": offset, "allowed_updates": '["message","callback_query"]'},
                )
                response.raise_for_status()
                for update in response.json().get("result", []):
                    dispatch = await gateway.handle_update(update)
                    try:
                        await client.answer_callback(dispatch.callback_query_id)
                        for reply in dispatch.replies:
                            await client.send(reply)
                        await gateway.mark_delivered(dispatch.update_id)
                        offset = max(offset, int(update["update_id"]) + 1)
                    except Exception:
                        await mark_update_attempt(get_engine(), dispatch.update_id)
                        # Keep the offset unchanged so Telegram returns this update
                        # again and the durable reply ledger can retry delivery.
                        break
    finally:
        await close_database_connection()


if __name__ == "__main__":
    asyncio.run(run())
