"""Conservative symptom-chat assistant for the patient Telegram surface."""

import asyncio
import os
import re
from datetime import date
from typing import Dict, List

from google import genai
from google.genai import types

from chatbot.prescription_assistant import EMERGENCY_RESPONSE, is_emergency_message


FALLBACK_RESPONSE = (
    "I'm here with you. Tell me what you're experiencing, when it started, and how severe "
    "it feels. I can help you organize the concern and find the right kind of doctor, "
    "although I can't diagnose or prescribe treatment."
)


def _fallback_response(message: str) -> str:
    """Keep basic conversation friendly even when Gemini is temporarily unavailable."""
    normalized = re.sub(r"\s+", " ", message.casefold()).strip()
    if re.search(r"\b(thanks|thank you|thx)\b", normalized):
        return "You're welcome. If anything else is worrying you, tell me in your own words."
    if re.search(r"\b(bye|goodbye|see you)\b", normalized):
        return "Take care. You can message me whenever you need help with your care at Medihub."
    if re.search(r"\b(how are you|who are you)\b", normalized):
        return "I'm your Medihub patient assistant. I can discuss a health concern and help with doctors, appointments, facilities, and your patient records."
    return FALLBACK_RESPONSE


async def answer_medical_message(
    message: str, history: List[Dict[str, str]]
) -> str:
    """Return emergency guidance, a safe Gemini response, or a deterministic fallback."""
    if is_emergency_message(message):
        return EMERGENCY_RESPONSE
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback_response(message)

    def generate() -> str:
        client = genai.Client(api_key=api_key)
        contents = [
            types.Content(
                role="user" if item["role"] == "user" else "model",
                parts=[types.Part.from_text(text=item["content"])],
            )
            for item in history[-10:]
            if item.get("role") in {"user", "assistant"}
        ]
        contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=message)])
        )
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.2,
                system_instruction=f"""
You are a warm, attentive Medihub patient assistant chatting naturally in Telegram.
Today is {date.today().isoformat()}. Respond to the patient's actual words and use the
recent conversation for context. Ask at most one useful follow-up question at a time.
You may help a patient describe symptoms, suggest the type of specialist they may
consider, and encourage an in-person consultation.
Never diagnose, claim certainty, prescribe or change medicines, give dosages, or replace
a clinician. Do not invent hospital, doctor, appointment, facility, or prescription data.
Those operations are handled separately by the verified gateway. Do not tell the patient
to use slash commands; they can speak naturally. If symptoms may be an
emergency, tell the patient to call 108 or go to the nearest emergency department now.
Avoid robotic menus, repetitive disclaimers, and long lectures. Keep the response short,
empathetic, conversational, and suitable for Telegram.
""",
            ),
        )
        return response.text or _fallback_response(message)

    try:
        return await asyncio.to_thread(generate)
    except Exception:
        return _fallback_response(message)
