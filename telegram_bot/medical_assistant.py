"""Conservative symptom-chat assistant for the patient Telegram surface."""

import asyncio
import os
from datetime import date
from typing import Dict, List

from google import genai
from google.genai import types

from chatbot.prescription_assistant import EMERGENCY_RESPONSE, is_emergency_message


FALLBACK_RESPONSE = (
    "I can help you describe your symptoms and choose an appropriate doctor, but I cannot "
    "diagnose a disease or prescribe treatment. Tell me what you are experiencing, how long "
    "it has been happening, and how severe it is. Use /speciality to find a doctor."
)


async def answer_medical_message(
    message: str, history: List[Dict[str, str]]
) -> str:
    """Return emergency guidance, a safe Gemini response, or a deterministic fallback."""
    if is_emergency_message(message):
        return EMERGENCY_RESPONSE
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return FALLBACK_RESPONSE

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
You are the Medihub Telegram patient assistant. Today is {date.today().isoformat()}.
You may help a patient describe symptoms, ask concise follow-up questions, suggest the
type of medical specialist they may consider, and encourage an in-person consultation.
Never diagnose, claim certainty, prescribe or change medicines, give dosages, or replace
a clinician. Do not invent hospital, doctor, appointment, facility, or prescription data.
Those operations are handled by deterministic gateway commands. If symptoms may be an
emergency, tell the patient to call 108 or go to the nearest emergency department now.
Keep the response short, empathetic, and suitable for Telegram.
""",
            ),
        )
        return response.text or FALLBACK_RESPONSE

    try:
        return await asyncio.to_thread(generate)
    except Exception:
        return FALLBACK_RESPONSE

