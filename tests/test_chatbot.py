"""
Unit and integration test suite for Phase 6 Schedule-Assistant Chatbot.

Covering:
- Doctor's tool call for own doctor_id succeeds.
- Doctor's tool call for a DIFFERENT doctor_id is rejected before hitting DB.
- Hospital owner's tool call for a doctor in their own hospital succeeds.
- Hospital owner's tool call for a doctor in a DIFFERENT hospital is rejected.
- Chat session persistence and message history retrieval endpoints.
"""

import pytest
import pytest_asyncio
from bson import ObjectId

from chatbot.gemini_client import (
    GEMINI_NOT_CONFIGURED_RESPONSE,
    GEMINI_UNAVAILABLE_RESPONSE,
    run_chat_completion,
)
from chatbot.tools import execute_tool_call
from common.auth import create_access_token, hash_password
from core.constants import UserRole
from core.models.appointment_model import AppointmentModel
from core.models.doctor_profile_model import DoctorProfileModel
from core.models.hospital_model import HospitalModel
from core.models.prescription_model import PrescriptionModel
from core.models.user_model import UserModel


@pytest.mark.asyncio
async def test_schedule_assistant_requires_gemini_api_key(monkeypatch, setup_db):
    """Schedule assistant is strict Gemini-only and does not use local fallback."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = await run_chat_completion(
        engine=setup_db,
        current_user={
            "user_id": str(ObjectId()),
            "email": "doctor@example.com",
            "role": "doctor",
            "hospital_id": str(ObjectId()),
            "name": "Dr. Test",
        },
        messages_history=[],
        user_prompt="Show my schedule today",
    )

    assert result == GEMINI_NOT_CONFIGURED_RESPONSE


@pytest.mark.asyncio
async def test_schedule_assistant_hides_raw_gemini_network_errors(monkeypatch, setup_db):
    """Raw socket/Windows errors should never be shown in the chat bubble."""

    class BrokenModels:
        def generate_content(self, **_):
            raise OSError(
                "[WinError 10013] An attempt was made to access a socket in a way "
                "forbidden by its access permissions"
            )

    class BrokenGeminiClient:
        models = BrokenModels()

    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setattr(
        "chatbot.gemini_client.get_gemini_client",
        lambda: BrokenGeminiClient(),
    )

    result = await run_chat_completion(
        engine=setup_db,
        current_user={
            "user_id": str(ObjectId()),
            "email": "doctor@example.com",
            "role": "doctor",
            "hospital_id": str(ObjectId()),
            "name": "Dr. Test",
        },
        messages_history=[],
        user_prompt="Show my schedule today",
    )

    assert result == GEMINI_UNAVAILABLE_RESPONSE
    assert "WinError" not in result
    assert "socket" not in result.casefold()


@pytest.mark.asyncio
async def test_doctor_tool_call_own_doctor_id_succeeds(setup_db):
    """A doctor requesting appointments for their own doctor_id succeeds."""
    engine = setup_db

    hospital_id = str(ObjectId())
    doctor_user_id = str(ObjectId())

    # Create doctor user and profile
    doctor_user = UserModel(
        id=ObjectId(doctor_user_id),
        name="Dr. Alice Smith",
        email="dr.alice@clinic.com",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.DOCTOR,
        hospital_id=hospital_id,
    )
    await engine.save(doctor_user)

    profile = DoctorProfileModel(
        user_id=doctor_user_id,
        hospital_id=hospital_id,
        specialization="Cardiology",
        consultation_fee="Rs. 500",
    )
    await engine.save(profile)
    profile_id = str(profile.id)

    # Context payload extracted from JWT
    doctor_user_context = {
        "user_id": doctor_user_id,
        "email": "dr.alice@clinic.com",
        "role": "doctor",
        "hospital_id": hospital_id,
        "name": "Dr. Alice Smith",
    }

    # Tool call using doctor profile_id
    res_profile = await execute_tool_call(
        engine=engine,
        current_user=doctor_user_context,
        tool_name="get_appointments",
        tool_args={
            "doctor_id": profile_id,
            "start_date": "2026-08-10",
            "end_date": "2026-08-10",
        },
    )
    assert "error" not in res_profile or res_profile.get("status") != "UNAUTHORIZED"
    assert res_profile.get("doctor_id") == profile_id

    # Tool call using doctor user_id
    res_user = await execute_tool_call(
        engine=engine,
        current_user=doctor_user_context,
        tool_name="get_appointments",
        tool_args={
            "doctor_id": doctor_user_id,
            "start_date": "2026-08-10",
            "end_date": "2026-08-10",
        },
    )
    assert "error" not in res_user or res_user.get("status") != "UNAUTHORIZED"
    assert res_user.get("doctor_id") == doctor_user_id


@pytest.mark.asyncio
async def test_doctor_tool_call_different_doctor_id_rejected(setup_db):
    """A doctor requesting appointments for a DIFFERENT doctor_id is rejected before hitting DB."""
    engine = setup_db

    hospital_id = str(ObjectId())
    doctor1_id = str(ObjectId())
    other_doctor_id = str(ObjectId())

    doctor_user_context = {
        "user_id": doctor1_id,
        "email": "dr.alice@clinic.com",
        "role": "doctor",
        "hospital_id": hospital_id,
        "name": "Dr. Alice Smith",
    }

    res = await execute_tool_call(
        engine=engine,
        current_user=doctor_user_context,
        tool_name="get_appointments",
        tool_args={
            "doctor_id": other_doctor_id,
            "start_date": "2026-08-10",
            "end_date": "2026-08-10",
        },
    )

    assert res.get("status") == "UNAUTHORIZED"
    assert "Access Denied" in res.get("error", "")


@pytest.mark.asyncio
async def test_hospital_owner_tool_call_own_hospital_doctor_succeeds(setup_db):
    """A hospital owner requesting appointments for a doctor in their own hospital succeeds."""
    engine = setup_db

    hospital_id = str(ObjectId())
    owner_id = str(ObjectId())
    doc_user_id = str(ObjectId())

    # Create doctor under this hospital
    doc_profile = DoctorProfileModel(
        user_id=doc_user_id,
        hospital_id=hospital_id,
        specialization="Pediatrics",
        consultation_fee="Rs. 400",
    )
    await engine.save(doc_profile)
    doc_profile_id = str(doc_profile.id)

    owner_context = {
        "user_id": owner_id,
        "email": "owner@hospital.com",
        "role": "hospital_owner",
        "hospital_id": hospital_id,
        "name": "Hospital Owner",
    }

    res = await execute_tool_call(
        engine=engine,
        current_user=owner_context,
        tool_name="get_appointments",
        tool_args={
            "doctor_id": doc_profile_id,
            "start_date": "2026-08-10",
            "end_date": "2026-08-10",
        },
    )

    assert "error" not in res or res.get("status") != "UNAUTHORIZED"
    assert res.get("doctor_id") == doc_profile_id


@pytest.mark.asyncio
async def test_hospital_owner_tool_call_different_hospital_doctor_rejected(setup_db):
    """A hospital owner requesting appointments for a doctor in a DIFFERENT hospital is rejected."""
    engine = setup_db

    hospital_a_id = str(ObjectId())
    hospital_b_id = str(ObjectId())
    owner_a_id = str(ObjectId())
    doc_b_user_id = str(ObjectId())

    # Doctor in Hospital B
    doc_b_profile = DoctorProfileModel(
        user_id=doc_b_user_id,
        hospital_id=hospital_b_id,
        specialization="Dermatology",
        consultation_fee="Rs. 600",
    )
    await engine.save(doc_b_profile)
    doc_b_profile_id = str(doc_b_profile.id)

    # Owner of Hospital A
    owner_a_context = {
        "user_id": owner_a_id,
        "email": "owner_a@hospital.com",
        "role": "hospital_owner",
        "hospital_id": hospital_a_id,
        "name": "Owner Hospital A",
    }

    res = await execute_tool_call(
        engine=engine,
        current_user=owner_a_context,
        tool_name="get_appointments",
        tool_args={
            "doctor_id": doc_b_profile_id,
            "start_date": "2026-08-10",
            "end_date": "2026-08-10",
        },
    )

    assert res.get("status") == "UNAUTHORIZED"
    assert "Access Denied" in res.get("error", "")


@pytest.mark.asyncio
async def test_chat_schedule_endpoint_and_sessions(async_client, booking_context):
    """Test POST /v1/chat/schedule, GET /v1/chat/schedule/sessions, and GET session history."""
    hospital_id = booking_context["hospital_id"]
    doctor_profile_id = booking_context["doctor_id"]

    # Log in as doctor created in booking_context
    doc_login = await async_client.post(
        "/api/v1/login",
        json={"email": "dr.booking@test.com", "password": "Doctor@Test1234"},
    )
    assert doc_login.status_code == 200, f"Doctor login failed: {doc_login.text}"
    token = doc_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Post first chat message
    chat_resp = await async_client.post(
        "/api/v1/chat/schedule",
        json={"message": "What is my appointment schedule for today?"},
        headers=headers,
    )
    assert chat_resp.status_code == 200, f"Chat request failed: {chat_resp.text}"
    body = chat_resp.json()
    assert "session_id" in body
    assert "response" in body
    session_id = body["session_id"]
    assert len(body["messages"]) >= 2  # user msg + assistant msg

    # 2. Get list of sessions
    sessions_resp = await async_client.get(
        "/api/v1/chat/schedule/sessions",
        headers=headers,
    )
    assert sessions_resp.status_code == 200
    sessions_list = sessions_resp.json()
    assert any(s["session_id"] == session_id for s in sessions_list)

    # 3. Get messages for the session
    msgs_resp = await async_client.get(
        f"/api/v1/chat/schedule/sessions/{session_id}",
        headers=headers,
    )
    assert msgs_resp.status_code == 200
    msgs_list = msgs_resp.json()
    assert len(msgs_list) >= 2
    assert msgs_list[0]["role"] == "user"


@pytest.mark.asyncio
async def test_patient_prescription_chat_endpoint_uses_patient_identity(
    async_client,
    setup_db,
    monkeypatch,
):
    """Prescription chat reads stored records for the JWT patient only."""
    engine = setup_db
    monkeypatch.setattr(
        "chatbot.prescription_assistant.search_prescriptions_rag",
        lambda **_: (_ for _ in ()).throw(AssertionError("Web chat must not call RAG embeddings")),
    )
    monkeypatch.setattr(
        "chatbot.prescription_assistant._generate_grounded_answer",
        lambda *_: (_ for _ in ()).throw(RuntimeError("Gemini unavailable")),
    )

    signup = await async_client.post(
        "/api/v1/signup",
        json={
            "name": "Prescription Chat Patient",
            "email": "prescription.chat.patient@example.com",
            "password": "Password123!",
        },
    )
    assert signup.status_code == 201, signup.text
    patient_id = signup.json()["user_id"]

    await engine.save(
        PrescriptionModel(
            hospital_id=str(ObjectId()),
            doctor_id=str(ObjectId()),
            doctor_name="Dr. Prescription",
            patient_id=patient_id,
            patient_name="Prescription Chat Patient",
            appointment_id=str(ObjectId()),
            date="2026-08-12",
            diagnosis="Viral fever",
            medications=[
                {
                    "medicine_name": "Paracetamol",
                    "dosage": "500mg",
                    "frequency": "1-0-1 after meals",
                    "duration": "3 days",
                    "instructions": "After food",
                }
            ],
            notes="Drink fluids.",
            follow_up_date="2026-08-19",
            pdf_url="/api/v1/patient/prescriptions/example/pdf-file",
        )
    )
    await engine.save(
        PrescriptionModel(
            hospital_id=str(ObjectId()),
            doctor_id=str(ObjectId()),
            doctor_name="Dr. Other",
            patient_id=str(ObjectId()),
            patient_name="Other Patient",
            appointment_id=str(ObjectId()),
            date="2026-08-12",
            diagnosis="Other diagnosis",
            medications=[
                {
                    "medicine_name": "Ibuprofen",
                    "dosage": "400mg",
                    "frequency": "Once daily",
                    "duration": "1 day",
                }
            ],
            pdf_url="/api/v1/patient/prescriptions/other/pdf-file",
        )
    )

    login = await async_client.post(
        "/api/v1/login",
        json={
            "email": "prescription.chat.patient@example.com",
            "password": "Password123!",
        },
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    chat_resp = await async_client.post(
        "/api/v1/chat/prescriptions",
        json={"message": "What medicines are documented for me?"},
        headers=headers,
    )

    assert chat_resp.status_code == 200, chat_resp.text
    body = chat_resp.json()
    session_id = body["session_id"]
    assert body["messages"][-1]["role"] == "assistant"
    assistant_content = body["messages"][-1]["content"]
    assert "Paracetamol" in assistant_content
    assert "Timing: Morning" in assistant_content
    assert "Ibuprofen" not in assistant_content
    assert "Dr. Prescription" in assistant_content

    sessions_resp = await async_client.get(
        "/api/v1/chat/prescriptions/sessions",
        headers=headers,
    )
    assert sessions_resp.status_code == 200
    sessions = sessions_resp.json()
    assert any(
        s["session_id"] == session_id and s["assistant_type"] == "prescription"
        for s in sessions
    )

    history_resp = await async_client.get(
        f"/api/v1/chat/prescriptions/sessions/{session_id}",
        headers=headers,
    )
    assert history_resp.status_code == 200
    assert len(history_resp.json()) == 2


@pytest.mark.asyncio
async def test_patient_tool_call_own_appointments_succeeds(setup_db):
    """A patient requesting their own appointments via get_patient_appointments or get_appointments succeeds."""
    engine = setup_db

    hospital_id = str(ObjectId())
    patient_id = str(ObjectId())
    doctor_id = str(ObjectId())

    # Create appointment for this patient
    appt = AppointmentModel(
        hospital_id=hospital_id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        patient_name="Patient User",
        date="2026-08-12",
        slot="10:00 AM",
        reason="General Checkup",
        temperature="98.6",
        symptoms=[],
    )
    await engine.save(appt)

    patient_context = {
        "user_id": patient_id,
        "email": "patient@clinic.com",
        "role": "patient",
        "hospital_id": hospital_id,
        "name": "Patient User",
    }

    # Test direct get_patient_appointments tool execution
    res = await execute_tool_call(
        engine=engine,
        current_user=patient_context,
        tool_name="get_patient_appointments",
        tool_args={"start_date": "2026-08-12", "end_date": "2026-08-12"},
    )
    assert res.get("total_appointments") == 1
    assert res["appointments"][0]["patient_name"] == "Patient User"

    # Test get_appointments routing for patient role
    res_alt = await execute_tool_call(
        engine=engine,
        current_user=patient_context,
        tool_name="get_appointments",
        tool_args={"doctor_id": patient_id, "start_date": "2026-08-12", "end_date": "2026-08-12"},
    )
    assert res_alt.get("total_appointments") == 1


@pytest.mark.asyncio
async def test_get_available_slots_tool_succeeds(setup_db):
    """get_available_slots tool returns available appointment slots for a given date."""
    engine = setup_db

    hospital_id = str(ObjectId())
    patient_context = {
        "user_id": str(ObjectId()),
        "email": "user@clinic.com",
        "role": "patient",
        "hospital_id": hospital_id,
        "name": "User",
    }

    res = await execute_tool_call(
        engine=engine,
        current_user=patient_context,
        tool_name="get_available_slots",
        tool_args={"date": "2026-08-15"},
    )
    assert "available_slots" in res
    assert res.get("date") == "2026-08-15"


@pytest.mark.asyncio
async def test_gemini_model_fallback_on_quota_error(monkeypatch, setup_db):
    """When the primary Gemini model fails with a 429 quota error, fallback model succeeds."""
    attempted_models = []

    class MockModels:
        def generate_content(self, model, contents, config):
            attempted_models.append(model)
            if model == "gemini-3.6-flash":
                raise RuntimeError("429 RESOURCE_EXHAUSTED: Quota exceeded for gemini-3.6-flash")
            
            # Fallback model succeeds
            class Candidate:
                content = "Fallback success content"
            class Response:
                function_calls = None
                candidates = [Candidate()]
                text = "Fallback Gemini Answer"
            return Response()

    class MockGeminiClient:
        models = MockModels()

    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite")
    monkeypatch.setattr(
        "chatbot.gemini_client.get_gemini_client",
        lambda: MockGeminiClient(),
    )

    result = await run_chat_completion(
        engine=setup_db,
        current_user={
            "user_id": str(ObjectId()),
            "email": "doctor@example.com",
            "role": "doctor",
            "hospital_id": str(ObjectId()),
            "name": "Dr. Test",
        },
        messages_history=[],
        user_prompt="Show my schedule today",
    )

    assert result == "Fallback Gemini Answer"
    assert attempted_models[0] == "gemini-3.6-flash"
    assert "gemini-3.1-flash-lite" in attempted_models
    assert len(attempted_models) >= 2
