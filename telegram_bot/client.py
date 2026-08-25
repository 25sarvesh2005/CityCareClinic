"""Minimal async client for the official Telegram Bot HTTP API."""

import os
from typing import Optional

import httpx

from telegram_bot.schemas import TelegramReply


class TelegramClient:
    """Deliver gateway replies without adding another Telegram SDK dependency."""

    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")
        root = (base_url or os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org")).rstrip("/")
        self.base_url = f"{root}/bot{self.token}"

    async def answer_callback(self, callback_query_id: Optional[str]) -> None:
        """Stop Telegram's callback-button loading spinner."""
        if not callback_query_id:
            return
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{self.base_url}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id},
            )
            response.raise_for_status()

    async def send(self, reply: TelegramReply) -> None:
        """Send text in Telegram-sized chunks, attaching buttons to the last chunk."""
        chunks = [reply.text[index:index + 4000] for index in range(0, len(reply.text), 4000)] or [""]
        async with httpx.AsyncClient(timeout=30) as client:
            for index, chunk in enumerate(chunks):
                payload = {"chat_id": reply.chat_id, "text": chunk}
                if index == len(chunks) - 1 and reply.reply_markup:
                    payload["reply_markup"] = reply.reply_markup
                response = await client.post(f"{self.base_url}/sendMessage", json=payload)
                response.raise_for_status()

