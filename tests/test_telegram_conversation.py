"""Unit tests for deterministic natural-language workflow helpers."""

from datetime import date

from telegram_bot.conversation import (
    detect_intent,
    parse_natural_date,
    parse_natural_time,
    parse_symptoms,
    parse_temperature,
)


def test_natural_intents_cover_patient_operations():
    assert detect_intent("show me the hospitals").name == "hospitals"
    assert detect_intent("which doctors are available?").name == "doctors"
    specialist = detect_intent("find me a heart specialist")
    assert specialist.name == "specialization"
    assert specialist.specialization == "cardio"
    assert detect_intent("I want to schedule a consultation").name == "book"
    assert detect_intent("when is my next appointment?").name == "appointments"
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
