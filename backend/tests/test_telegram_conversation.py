"""Unit tests for deterministic natural-language workflow helpers."""

from datetime import date

import pytest

from telegram_bot.conversation import (
    detect_intent,
    parse_natural_date,
    parse_natural_time,
    parse_symptoms,
    parse_temperature,
)
from telegram_bot.medical_assistant import resolve_patient_message


def test_natural_intents_cover_patient_operations():
    assert detect_intent("am I registered?").name == "account_status"
    assert detect_intent("am i registerd").name == "account_status"
    assert detect_intent("what is my regesteration status").name == "account_status"
    assert (
        detect_intent("I want to know is my registration complete in your portal").name
        == "account_status"
    )
    assert (
        detect_intent("i want to konw is my registration completer in your portal").name
        == "account_status"
    )
    assert detect_intent("show me the hospitals").name == "hospitals"
    assert detect_intent("which doctors are available?").name == "doctors"
    specialist = detect_intent("find me a heart specialist")
    assert specialist.name == "specialization"
    assert specialist.specialization == "cardio"
    assert detect_intent("I want to schedule a consultation").name == "book"
    assert detect_intent("when is my next appointment?").name == "appointments"
    assert detect_intent("is my request approved?").name == "appointment_status"
    assert detect_intent("did the doctor accept my booking?").name == "appointment_status"
    assert detect_intent("what is my booking status?").name == "appointment_status"
    assert detect_intent("show my prescriptions").name == "prescriptions"
    assert detect_intent("what facilities does the hospital have?").name == "facilities"


def test_booking_values_accept_common_patient_wording():
    base = date(2026, 8, 26)
    assert parse_natural_date("tomorrow", today=base) == "2026-08-27"
    assert parse_natural_date("this Friday", today=base) == "2026-08-28"
    assert parse_natural_time("10:30 am") == "10:30"
    assert parse_natural_time("5:30 in the evening") == "17:30"
    assert parse_temperature("37.5 C") == 99.5
    assert parse_symptoms("fever, coughing and body pain") == [
        "fever",
        "cough",
        "bodyache",
    ]


@pytest.mark.asyncio
async def test_social_turns_do_not_depend_on_gemini(monkeypatch):
    class GeminiMustNotRun:
        def __init__(self, *args, **kwargs):
            raise AssertionError("A social acknowledgement must not call Gemini")

    monkeypatch.setenv("GEMINI_API_KEY", "configured-key")
    monkeypatch.setattr("telegram_bot.medical_assistant.genai.Client", GeminiMustNotRun)

    thanked = await resolve_patient_message("ok thankyou", [])
    acknowledged = await resolve_patient_message("got it", [])

    assert thanked.reply == "You're welcome! Message me anytime you need help with your care."
    assert acknowledged.reply == "Okay! What would you like help with next?"


@pytest.mark.asyncio
async def test_unknown_fallback_does_not_assume_a_health_problem(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    decision = await resolve_patient_message("can you repeat that another way", [])
    assert "didn't fully understand" in decision.reply
    assert "what you're experiencing" not in decision.reply
