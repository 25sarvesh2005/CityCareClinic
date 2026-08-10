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

from chatbot.tools import execute_tool_call
from common.auth import create_access_token, hash_password
from core.constants import UserRole
from core.models.appointment_model import AppointmentModel
from core.models.doctor_profile_model import DoctorProfileModel
from core.models.hospital_model import HospitalModel
from core.models.user_model import UserModel


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
