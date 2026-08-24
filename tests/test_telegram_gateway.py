"""End-to-end tests for the patient-only Telegram gateway."""

from datetime import date

import pytest

from core.models.appointment_model import AppointmentModel
from core.models.hospital_model import HospitalModel
from core.models.user_model import UserModel
from telegram_bot.gateway import TelegramGateway


pytestmark = pytest.mark.asyncio


def message(update_id: int, user_id: int, text: str) -> dict:
    """Build a minimal private Telegram message update."""
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "from": {"id": user_id, "username": f"patient{user_id}"},
            "chat": {"id": user_id, "type": "private"},
            "text": text,
        },
    }


def callback(update_id: int, user_id: int, data: str) -> dict:
    """Build a minimal Telegram inline-button callback update."""
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"callback-{update_id}",
            "from": {"id": user_id, "username": f"patient{user_id}"},
            "message": {
                "message_id": update_id - 1,
                "chat": {"id": user_id, "type": "private"},
            },
            "data": data,
        },
    }


async def dispatch(engine, update: dict):
    """Use a fresh gateway to prove state survives process/request boundaries."""
    return await TelegramGateway(engine).handle_update(update)


async def register_patient(engine, user_id: int, start_update: int = 100):
    """Complete Telegram-native registration without collecting a password."""
    await dispatch(engine, message(start_update, user_id, "/register"))
    await dispatch(engine, message(start_update + 1, user_id, "Telegram Patient"))
    await dispatch(
        engine,
        message(start_update + 2, user_id, f"telegram{user_id}@example.com"),
    )
    result = await dispatch(
        engine, message(start_update + 3, user_id, "+919876543210")
    )
    assert "Registration complete" in result.replies[0].text
    return await engine.find_one(
        UserModel, UserModel.telegram_user_id == str(user_id)
    )


async def test_telegram_registration_persists_identity_and_state(setup_db):
    patient = await register_patient(setup_db, 700001)
    assert patient is not None
    assert patient.role.value == "patient"
    assert patient.registration_source == "telegram"
    assert patient.phone_number == "+919876543210"
    assert patient.hashed_password


async def test_existing_patient_links_with_one_time_code(
    setup_db, async_client
):
    signup = await async_client.post(
        "/api/v1/signup",
        json={
            "name": "Existing Patient",
            "email": "existing.telegram@example.com",
            "password": "safe-password",
        },
    )
    assert signup.status_code == 201
    login = await async_client.post(
        "/api/v1/login",
        json={
            "email": "existing.telegram@example.com",
            "password": "safe-password",
        },
    )
    token = login.json()["access_token"]
    code_response = await async_client.post(
        "/api/v1/telegram/link-code",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert code_response.status_code == 200

    result = await dispatch(
        setup_db,
        message(200, 700002, f"/link {code_response.json()['code']}"),
    )
    assert "Linked securely" in result.replies[0].text
    patient = await setup_db.find_one(
        UserModel, UserModel.email == "existing.telegram@example.com"
    )
    assert patient.telegram_user_id == "700002"

    replay = await dispatch(
        setup_db,
        message(201, 700003, f"/link {code_response.json()['code']}"),
    )
    assert "invalid or expired" in replay.replies[0].text


async def test_doctor_specialization_and_facilities_are_patient_visible(
    setup_db, booking_context
):
    hospital = await setup_db.find_one(
        HospitalModel, HospitalModel.id == booking_context["hospital_id"]
    )
    if hospital is None:
        from bson import ObjectId

        hospital = await setup_db.find_one(
            HospitalModel, HospitalModel.id == ObjectId(booking_context["hospital_id"])
        )
    hospital.facilities = ["24/7 Pharmacy", "Diagnostic Lab"]
    hospital.services = ["General Medicine", "Vaccination"]
    await setup_db.save(hospital)

    specialist = await dispatch(
        setup_db, message(300, 700004, "/speciality general")
    )
    assert "Dr. Booking Test" in str(specialist.replies[0].reply_markup)

    facilities = await dispatch(
        setup_db,
        callback(301, 700004, f"facilities:{booking_context['hospital_id']}"),
    )
    assert "24/7 Pharmacy" in facilities.replies[0].text
    assert "Vaccination" in facilities.replies[0].text


async def test_registered_patient_books_only_after_explicit_confirmation(
    setup_db, booking_context
):
    user_id = 700005
    patient = await register_patient(setup_db, user_id, 400)
    hospital_id = booking_context["hospital_id"]
    doctor_id = booking_context["doctor_id"]
    appointment_date = date.today().isoformat()

    await dispatch(setup_db, callback(410, user_id, f"book:{hospital_id}:{doctor_id}"))
    await dispatch(setup_db, message(411, user_id, appointment_date))
    await dispatch(setup_db, callback(412, user_id, "slot:10:00"))
    await dispatch(
        setup_db,
        message(413, user_id, "Persistent fever and body pain"),
    )
    await dispatch(setup_db, message(414, user_id, "99.5"))
    summary = await dispatch(
        setup_db, message(415, user_id, "fever, bodyache")
    )
    assert "Confirm appointment" in summary.replies[0].text
    assert await setup_db.count(
        AppointmentModel, AppointmentModel.patient_id == str(patient.id)
    ) == 0

    confirmed = await dispatch(
        setup_db, callback(416, user_id, "confirm_booking")
    )
    assert "Appointment booked" in confirmed.replies[0].text
    assert await setup_db.count(
        AppointmentModel, AppointmentModel.patient_id == str(patient.id)
    ) == 1

    duplicate = await dispatch(
        setup_db, callback(416, user_id, "confirm_booking")
    )
    assert duplicate.replayed is True
    assert await setup_db.count(
        AppointmentModel, AppointmentModel.patient_id == str(patient.id)
    ) == 1


async def test_private_records_require_registration(setup_db):
    appointments = await dispatch(
        setup_db, message(500, 700006, "/appointments")
    )
    prescriptions = await dispatch(
        setup_db, message(501, 700006, "/prescriptions")
    )
    assert "Registration is required" in appointments.replies[0].text
    assert "Registration is required" in prescriptions.replies[0].text


async def test_emergency_message_uses_fixed_safety_response(setup_db, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = await dispatch(
        setup_db,
        message(600, 700007, "I have chest pain and cannot breathe"),
    )
    assert "call 108" in result.replies[0].text


async def test_webhook_rejects_invalid_secret(async_client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "correct-secret")
    response = await async_client.post(
        "/api/v1/telegram/webhook",
        json=message(700, 700008, "/start"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    assert response.status_code == 401


async def test_group_chat_is_rejected_to_protect_patient_privacy(setup_db):
    update = message(800, 700009, "/prescriptions")
    update["message"]["chat"] = {
        "id": -100123456789,
        "type": "supergroup",
    }
    result = await dispatch(setup_db, update)
    assert "only in a private chat" in result.replies[0].text
