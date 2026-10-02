"""End-to-end tests for the patient-only Telegram gateway."""

import asyncio
from datetime import date

import pytest

from core.constants import AppointmentStatus
from core.models.appointment_model import AppointmentModel
from core.models.hospital_model import HospitalModel
from core.models.user_model import UserModel
from telegram_bot.client import TelegramClient
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


async def test_link_code_is_atomic_under_concurrent_consumers(
    setup_db, async_client
):
    signup = await async_client.post(
        "/api/v1/signup",
        json={
            "name": "Concurrent Link Patient",
            "email": "concurrent.telegram@example.com",
            "password": "safe-password",
        },
    )
    assert signup.status_code == 201
    login = await async_client.post(
        "/api/v1/login",
        json={
            "email": "concurrent.telegram@example.com",
            "password": "safe-password",
        },
    )
    code_response = await async_client.post(
        "/api/v1/telegram/link-code",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    code = code_response.json()["code"]

    results = await asyncio.gather(
        dispatch(setup_db, message(210, 700020, f"/link {code}")),
        dispatch(setup_db, message(211, 700021, f"/link {code}")),
    )
    texts = [result.replies[0].text for result in results]
    assert sum("Linked securely" in text for text in texts) == 1
    assert sum("invalid or expired" in text for text in texts) == 1


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
    summary = await dispatch(setup_db, message(414, user_id, "99.5"))
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


async def test_concurrent_duplicate_update_runs_booking_effect_once(
    setup_db, booking_context
):
    user_id = 700022
    patient = await register_patient(setup_db, user_id, 900)
    hospital_id = booking_context["hospital_id"]
    doctor_id = booking_context["doctor_id"]

    await dispatch(setup_db, callback(910, user_id, f"book:{hospital_id}:{doctor_id}"))
    await dispatch(setup_db, message(911, user_id, date.today().isoformat()))
    await dispatch(setup_db, callback(912, user_id, "slot:10:00"))
    await dispatch(setup_db, message(913, user_id, "Persistent fever and body pain"))
    await dispatch(setup_db, message(914, user_id, "99.5"))
    await dispatch(setup_db, message(915, user_id, "fever, bodyache"))

    results = await asyncio.gather(
        dispatch(setup_db, callback(916, user_id, "confirm_booking")),
        dispatch(setup_db, callback(916, user_id, "confirm_booking")),
    )
    assert any(result.replayed for result in results)
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


async def test_valid_webhook_delivers_gateway_reply(async_client, monkeypatch):
    sent = []

    async def fake_send(_client, reply):
        sent.append(reply)

    async def fake_answer_callback(_client, _callback_query_id):
        return None

    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "correct-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(TelegramClient, "send", fake_send)
    monkeypatch.setattr(TelegramClient, "answer_callback", fake_answer_callback)

    response = await async_client.post(
        "/api/v1/telegram/webhook",
        json=message(701, 700008, "/start"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "correct-secret"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "duplicate": False}
    assert len(sent) == 1
    assert "Medihub Patient Assistant" in sent[0].text


async def test_group_chat_is_rejected_to_protect_patient_privacy(setup_db):
    update = message(800, 700009, "/prescriptions")
    update["message"]["chat"] = {
        "id": -100123456789,
        "type": "supergroup",
    }
    result = await dispatch(setup_db, update)
    assert "only in a private chat" in result.replies[0].text


async def test_natural_language_routes_patient_operations_without_commands(
    setup_db, booking_context, monkeypatch
):
    """Patients can discover and select doctors using ordinary text and numbers."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    greeting = await dispatch(setup_db, message(1000, 701000, "hello there"))
    assert "Talk to me normally" in greeting.replies[0].text

    specialists = await dispatch(
        setup_db,
        message(1001, 701000, "Can you find me a general physician?"),
    )
    assert "Dr. Booking Test" in specialists.replies[0].text
    assert "name or number" in specialists.replies[0].text

    selected = await dispatch(setup_db, message(1002, 701000, "number 1"))
    assert "Dr. Booking Test" in selected.replies[0].text
    assert "Specialization:" in selected.replies[0].text

    private_request = await dispatch(
        setup_db, message(1003, 701000, "show me my prescriptions")
    )
    assert "Registration is required" in private_request.replies[0].text
    assert private_request.replies[0].reply_markup is not None


async def test_registration_status_uses_verified_telegram_identity(setup_db):
    unlinked = await dispatch(
        setup_db, message(1050, 701050, "am I registered?")
    )
    assert "don't see a Medihub patient profile linked" in unlinked.replies[0].text
    assert unlinked.replies[0].reply_markup is not None

    await register_patient(setup_db, 701051, 1060)
    linked = await dispatch(
        setup_db,
        message(
            1070,
            701051,
            "I want to konw is my registration completer in your portal",
        ),
    )
    assert "registration is complete" in linked.replies[0].text
    assert "Telegram Patient" in linked.replies[0].text


async def test_appointment_approval_question_reports_latest_real_status(
    setup_db, booking_context
):
    user_id = 701052
    await register_patient(setup_db, user_id, 1200)
    hospital_id = booking_context["hospital_id"]
    doctor_id = booking_context["doctor_id"]

    await dispatch(setup_db, callback(1210, user_id, f"book:{hospital_id}:{doctor_id}"))
    await dispatch(setup_db, message(1211, user_id, date.today().isoformat()))
    await dispatch(setup_db, callback(1212, user_id, "slot:10:00"))
    await dispatch(setup_db, message(1213, user_id, "Persistent fever and body pain"))
    await dispatch(setup_db, message(1214, user_id, "99.5"))
    await dispatch(setup_db, message(1215, user_id, "fever, bodyache"))
    await dispatch(setup_db, callback(1216, user_id, "confirm_booking"))

    result = await dispatch(
        setup_db, message(1217, user_id, "is my request approved?")
    )
    reply = result.replies[0].text.casefold()
    assert "latest appointment request" in reply
    assert "pending" in reply
    assert "waiting for the doctor's approval" in reply

    appointment = await setup_db.find_one(
        AppointmentModel, AppointmentModel.patient_id == str((await setup_db.find_one(
            UserModel, UserModel.telegram_user_id == str(user_id)
        )).id)
    )
    appointment.status = AppointmentStatus.ACCEPTED
    await setup_db.save(appointment)

    prescription_result = await dispatch(
        setup_db,
        message(
            1218,
            user_id,
            "can you tell me whether the doctor has any prescription for my previous visit",
        ),
    )
    prescription_reply = prescription_result.replies[0].text.casefold()
    assert "accepted appointment" in prescription_reply
    assert "hasn't submitted a prescription" in prescription_reply
    assert "if your visit already happened" in prescription_reply


async def test_complete_booking_can_be_done_as_a_natural_conversation(
    setup_db, booking_context
):
    """Buttons remain optional throughout registration, discovery, and booking."""
    user_id = 701001
    started = await dispatch(
        setup_db, message(1100, user_id, "I want to create a patient account")
    )
    assert "full name" in started.replies[0].text
    await dispatch(setup_db, message(1101, user_id, "My name is Natural Patient"))
    await dispatch(
        setup_db, message(1102, user_id, "natural.patient@example.com")
    )
    registered = await dispatch(
        setup_db, message(1103, user_id, "+919812345678")
    )
    assert "Welcome, Natural Patient" in registered.replies[0].text

    hospitals = await dispatch(
        setup_db, message(1104, user_id, "I need to book an appointment")
    )
    assert "Which hospital" in hospitals.replies[0].text
    doctors = await dispatch(setup_db, message(1105, user_id, "1"))
    assert "Dr. Booking Test" in doctors.replies[0].text
    doctor = await dispatch(setup_db, message(1106, user_id, "first"))
    assert "Specialization:" in doctor.replies[0].text

    booking = await dispatch(
        setup_db, message(1107, user_id, "please book an appointment")
    )
    assert "what day works" in booking.replies[0].text
    available = await dispatch(setup_db, message(1108, user_id, "today"))
    assert "Type a time" in available.replies[0].text
    reason = await dispatch(setup_db, message(1109, user_id, "10 am"))
    assert "help you with" in reason.replies[0].text
    await dispatch(
        setup_db,
        message(1110, user_id, "I have had a persistent fever and body pain"),
    )
    summary = await dispatch(setup_db, message(1111, user_id, "37.5 C"))
    assert "Reply 'yes'" in summary.replies[0].text
    assert "Temperature: 99.5" in summary.replies[0].text

    confirmed = await dispatch(setup_db, message(1113, user_id, "yes, book it"))
    assert "Appointment booked" in confirmed.replies[0].text
    patient = await setup_db.find_one(
        UserModel, UserModel.telegram_user_id == str(user_id)
    )
    assert await setup_db.count(
        AppointmentModel, AppointmentModel.patient_id == str(patient.id)
    ) == 1


async def test_booking_accepts_multiple_details_in_one_message(
    setup_db, booking_context
):
    user_id = 701060
    await register_patient(setup_db, user_id, 1300)
    hospital_id = booking_context["hospital_id"]
    doctor_id = booking_context["doctor_id"]

    await dispatch(setup_db, callback(1310, user_id, f"book:{hospital_id}:{doctor_id}"))
    partial = await dispatch(
        setup_db, message(1311, user_id, "tomorrow and for 7pm")
    )
    partial_text = partial.replies[0].text
    assert "at 19:00" in partial_text
    assert "What would you like the doctor to help you with?" in partial_text

    # Start over and provide all required booking details in a single natural sentence.
    await dispatch(setup_db, message(1312, user_id, "/cancel"))
    await dispatch(setup_db, callback(1313, user_id, f"book:{hospital_id}:{doctor_id}"))
    complete = await dispatch(
        setup_db,
        message(
            1314,
            user_id,
            "tomorrow at 7 pm for persistent fever and cough, temperature 101 F",
        ),
    )
    summary = complete.replies[0].text
    assert "Confirm appointment" in summary
    assert "Time: 19:00" in summary
    assert "Reason: persistent fever and cough" in summary
    assert "Temperature: 101.0 °F" in summary
    assert "Symptoms: fever, cough" in summary
