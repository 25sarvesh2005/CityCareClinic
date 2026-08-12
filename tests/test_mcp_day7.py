"""End-to-end checks for CityCare's appointment-focused MCP server."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from bson import ObjectId

import mcp_server.server as citycare_mcp
from core.models.appointment_model import AppointmentModel
from mcp_server.tools.appointment_tools import (
    book_appointment_via_api,
    get_available_slots_from_api,
    list_hospital_doctors_from_api,
    search_hospitals_from_api,
)


def _mcp_context(authorization: str) -> SimpleNamespace:
    """Minimal HTTP-shaped MCP context used to exercise the registered tool handler."""
    return SimpleNamespace(
        request_context=SimpleNamespace(request=SimpleNamespace(headers={"authorization": authorization}))
    )


@pytest.mark.asyncio
async def test_inspector_capabilities_include_tools_resource_and_prompt():
    """The server exports the three MCP capability types requested for Day 7."""
    tools = await citycare_mcp.mcp.get_tools()
    resources = await citycare_mcp.mcp.get_resources()
    prompts = await citycare_mcp.mcp.get_prompts()

    assert {"search_hospitals", "list_hospital_doctors", "get_available_slots", "book_appointment"}.issubset(tools)
    assert "citycare://appointment-booking-policy" in resources
    assert "book_appointment_safely" in prompts


@pytest.mark.asyncio
async def test_discovery_wrappers_return_patient_selectable_ids(async_client, booking_context):
    """MCP exposes the public discovery path needed before checking availability."""
    hospitals = await search_hospitals_from_api("Test Booking", client=async_client)
    assert hospitals == [
        {
            "hospital_id": booking_context["hospital_id"],
            "name": "Test Booking Hospital",
            "city": "Testcity",
            "address": "1 Test Avenue",
            "contact_number": "+91-00-1111-2222",
            "is_active": True,
        }
    ]

    doctors = await list_hospital_doctors_from_api(booking_context["hospital_id"], client=async_client)
    assert len(doctors) == 1
    assert doctors[0]["profile_id"] == booking_context["doctor_id"]
    assert doctors[0]["name"] == "Dr. Booking Test"


@pytest.mark.asyncio
async def test_booking_via_registered_mcp_tool_is_persisted(
    async_client, booking_context, setup_db, monkeypatch
):
    """A booking made by the MCP tool reaches Day-4 API validation and MongoDB."""
    patient_email = "mcp.patient@example.com"
    password = "SecurePassword123!"
    signup_response = await async_client.post(
        "/api/v1/signup",
        json={"name": "MCP Test Patient", "email": patient_email, "password": password},
    )
    assert signup_response.status_code == 201

    login_response = await async_client.post(
        "/api/v1/login",
        json={"email": patient_email, "password": password},
    )
    assert login_response.status_code == 200
    authorization = f"Bearer {login_response.json()['access_token']}"

    appointment_date = (date.today() + timedelta(days=1)).isoformat()
    availability = await get_available_slots_from_api(
        booking_context["hospital_id"],
        booking_context["doctor_id"],
        appointment_date,
        client=async_client,
    )
    slot = availability["available_slots"][0]

    async def call_test_api(**kwargs):
        return await book_appointment_via_api(**kwargs, client=async_client)

    monkeypatch.setattr(citycare_mcp, "book_appointment_via_api", call_test_api)
    tool = await citycare_mcp.mcp.get_tool("book_appointment")
    booking = await tool.fn(
        hospital_id=booking_context["hospital_id"],
        doctor_id=booking_context["doctor_id"],
        appointment_date=appointment_date,
        slot=slot,
        reason="Persistent fever and cough for three days",
        temperature=99.1,
        symptoms=["fever", "cough"],
        ctx=_mcp_context(authorization),
    )

    stored = await setup_db.find_one(AppointmentModel, AppointmentModel.id == ObjectId(booking["appointment_id"]))
    assert stored is not None
    assert stored.patient_name == "MCP Test Patient"
    assert stored.date == appointment_date
    assert stored.slot == slot


@pytest.mark.asyncio
async def test_booking_wrapper_forwards_no_patient_identity(async_client, booking_context):
    """The MCP wrapper never accepts patient_id or patient_name from a model."""
    with pytest.raises(TypeError):
        await book_appointment_via_api(
            hospital_id=booking_context["hospital_id"],
            doctor_id=booking_context["doctor_id"],
            appointment_date=(date.today() + timedelta(days=1)).isoformat(),
            slot="10:00",
            reason="This must not be accepted without a real patient token",
            temperature=98.6,
            symptoms=["fever"],
            authorization="Bearer token",
            patient_id="manipulated-patient-id",
            client=async_client,
        )
