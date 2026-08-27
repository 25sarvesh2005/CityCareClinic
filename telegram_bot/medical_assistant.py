"""Contextual Gemini router and conservative health assistant for Telegram."""

import asyncio
from datetime import date
import logging
import os
import re
from typing import Dict, List, Literal, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from chatbot.prescription_assistant import EMERGENCY_RESPONSE, is_emergency_message


LOGGER = logging.getLogger(__name__)

PatientIntent = Literal[
    "medical_chat",
    "account_status",
    "appointments",
    "appointment_status",
    "prescriptions",
    "hospitals",
    "doctors",
    "specialization",
    "facilities",
    "book",
    "register",
    "link",
    "help",
    "greeting",
]


class AssistantDecision(BaseModel):
    """Structured model decision; the gateway still authorizes and executes actions."""

    intent: PatientIntent
    specialization: Optional[str] = Field(
        default=None,
        description="Requested medical specialty, only when explicitly stated or clearly implied.",
    )
    reply: Optional[str] = Field(
        default=None,
        description="Natural reply only for medical_chat, greeting, or help.",
    )


FALLBACK_RESPONSE = (
    "I didn't fully understand that. You can ask me naturally about registration, doctors, "
    "appointments, facilities, prescriptions, or tell me about a health concern."
)


def _normalized_text(message: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", message.casefold())).strip()


def _social_reply(message: str) -> Optional[str]:
    """Handle ordinary social turns instantly, without relying on an AI request."""
    normalized = _normalized_text(message)
    compact = normalized.replace(" ", "")
    if any(
        marker in compact
        for marker in ("thankyou", "thanku", "thankyouu", "thanks", "thx", "thnx", "tysm")
    ):
        return "You're welcome! Message me anytime you need help with your care."
    if re.search(r"\b(bye|goodbye|see you)\b", normalized):
        return "Take care. You can message me whenever you need help with your care at Medihub."
    if re.search(r"\b(how are you|who are you)\b", normalized):
        return (
            "I'm your Medihub patient assistant. I can discuss a health concern and help "
            "with doctors, appointments, facilities, registration, and patient records."
        )
    if normalized in {
        "ok",
        "okay",
        "alright",
        "all right",
        "got it",
        "i understand",
        "understood",
        "sounds good",
        "cool",
        "fine",
    }:
        return "Okay! What would you like help with next?"
    return None


def _fallback_response(message: str) -> str:
    """Stay useful without wrongly treating every unknown sentence as a symptom."""
    social = _social_reply(message)
    if social:
        return social
    normalized = _normalized_text(message)
    if re.search(
        r"\b(pain|ache|fever|cough|cold|rash|bleed|bleeding|dizz|nause|vomit|"
        r"breath|sick|ill|hurt|symptom|head|chest|stomach|throat|skin|body|"
        r"feel|feeling|unwell|temperature)\b",
        normalized,
    ):
        return (
            "I'm here with you. Tell me when this started and how severe it feels. "
            "I can help you organize the concern and find the right kind of doctor, "
            "although I can't diagnose or prescribe treatment."
        )
    return FALLBACK_RESPONSE


def _timeout_seconds() -> float:
    try:
        configured = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "10"))
    except ValueError:
        configured = 10
    return min(max(configured, 3), 30)


def _candidate_models() -> List[str]:
    """Return the configured primary and a fast, known-working fallback model."""
    candidates = [
        os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip(),
        os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite").strip(),
    ]
    return list(dict.fromkeys(model for model in candidates if model))


async def resolve_patient_message(
    message: str, history: List[Dict[str, str]]
) -> AssistantDecision:
    """Classify one contextual turn and optionally produce its safe medical reply."""
    if is_emergency_message(message):
        return AssistantDecision(intent="medical_chat", reply=EMERGENCY_RESPONSE)

    social_reply = _social_reply(message)
    if social_reply:
        return AssistantDecision(intent="greeting", reply=social_reply)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return AssistantDecision(intent="medical_chat", reply=_fallback_response(message))

    timeout = _timeout_seconds()
    contents = [
        types.Content(
            role="user" if item["role"] == "user" else "model",
            parts=[types.Part.from_text(text=item["content"])],
        )
        for item in history[-10:]
        if item.get("role") in {"user", "assistant"} and item.get("content")
    ]
    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=message)])
    )
    config = types.GenerateContentConfig(
        temperature=0.35,
        max_output_tokens=450,
        response_mime_type="application/json",
        response_schema=AssistantDecision,
        system_instruction=f"""
You are Medihub's warm, capable patient-care assistant on Telegram. You should feel like
a thoughtful human care coordinator who is genuinely listening, while being honest that
you are an assistant rather than a doctor. Today is {date.today().isoformat()}.
Use both the current message and the recent conversation; never ask for information the
patient has already provided.

Classify the patient's goal into exactly one intent:
- account_status: asks whether their patient registration/account/link is complete or active.
- appointments: asks to list, view, recall, or find their appointments.
- appointment_status: asks whether a booking/request was approved, accepted, rejected,
  cancelled, completed, pending, or reviewed by the doctor. A vague phrase such as
  "is my request approved?" normally refers to the most recent appointment request.
- prescriptions: asks to view or discuss their stored prescriptions or prescribed medicines.
- hospitals: asks to find/list hospitals or clinics.
- doctors: asks to find/list available doctors without a particular specialty.
- specialization: requests a kind of specialist; put the specialty in specialization.
- facilities: asks about hospital facilities, services, labs, pharmacy, or departments.
- book: wants to make/schedule an appointment or consultation.
- register: wants to create a new patient account.
- link: wants to connect an existing Medihub web account to Telegram.
- help: asks what the assistant can do.
- greeting: a greeting or light social message.
- medical_chat: symptoms, health concerns, general medical conversation, or anything that
  is not a Medihub patient operation.

For operational intents, do not invent data and normally leave reply empty because the
verified gateway will fetch real records and perform authorization. Never produce IDs.

For medical_chat, greeting, or help, write the reply as natural conversation:
- React specifically to what the patient just said; do not use a generic sympathy line.
- Use simple everyday language and match the patient's language and tone when practical.
- Keep most replies to 2-4 short sentences suitable for Telegram.
- Ask no more than one useful question at a time. Choose the question that best helps
  understand severity, duration, location, associated symptoms, or the right next step.
- Refer naturally to earlier details when present so the conversation feels continuous.
- If useful, offer a concrete next step such as monitoring symptoms, basic low-risk
  self-care, finding the appropriate specialist, or booking an appointment.
- Mention urgent warning signs only when they are relevant to this patient's symptoms.
- Never diagnose or claim certainty. Never prescribe, change medicines, or give dosages.
- Do not repeat a medical disclaimer in every message. Do not begin every reply with
  "I'm sorry to hear that" or "I'm here with you."
- Do not present a menu, command list, or long lecture unless the patient asks for one.
- Never claim that a record, appointment, doctor, or facility exists without gateway data.
""",
    )

    errors = []
    for model in _candidate_models():
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        try:
            async with client.aio as async_client:
                response = await asyncio.wait_for(
                    async_client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config,
                    ),
                    timeout=timeout + 1,
                )
            if isinstance(response.parsed, AssistantDecision):
                decision = response.parsed
            else:
                response_text = response.text or ""
                json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                decision = AssistantDecision.model_validate_json(
                    json_match.group(0) if json_match else response_text
                )
            if decision.intent in {"medical_chat", "greeting", "help"} and not decision.reply:
                decision.reply = _fallback_response(message)
            return decision
        except Exception as error:
            errors.append(f"{model}={type(error).__name__}: {error}")
            LOGGER.warning(
                "Gemini Telegram model %s failed (%s); trying fallback if available.",
                model,
                type(error).__name__,
            )

    LOGGER.error("All Gemini Telegram models failed: %s", " | ".join(errors))
    return AssistantDecision(intent="medical_chat", reply=_fallback_response(message))


async def answer_medical_message(
    message: str, history: List[Dict[str, str]]
) -> str:
    """Backward-compatible text-only wrapper for callers that need a medical reply."""
    decision = await resolve_patient_message(message, history)
    return decision.reply or _fallback_response(message)
