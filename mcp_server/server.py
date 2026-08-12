"""HTTP MCP server exposing CityCare's authorized clinic tools."""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, AsyncIterator

from dotenv import load_dotenv
from fastmcp import Context, FastMCP
from pydantic import Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from core.database.database import close_database_connection, connect_to_database
from mcp_server.tools.appointment_tools import (
    book_appointment_via_api,
    get_available_slots_from_api,
    get_doctor_schedule_for_requester,
    list_hospital_doctors_from_api,
    list_patient_appointments_for_requester,
    search_hospitals_from_api,
)
from mcp_server.tools.auth import (
    MCPAuthorizationError,
    authorization_header_from_mcp_context,
    requester_from_mcp_context,
)
from mcp_server.tools.prescription_tools import (
    get_prescription_for_requester,
    search_prescriptions_for_requester,
)


@asynccontextmanager
async def database_lifespan(_: FastMCP) -> AsyncIterator[None]:
    await connect_to_database()
    try:
        yield
    finally:
        await close_database_connection()


mcp = FastMCP(
    "CityCare Clinic MCP",
    instructions=(
        "Use get_available_slots before booking. Call book_appointment only after the patient "
        "explicitly confirms an exact available slot. Booking identity is taken only from the "
        "verified CityCare JWT, never from tool arguments."
    ),
    lifespan=database_lifespan,
)


@mcp.resource(
    "citycare://appointment-booking-policy",
    name="CityCare appointment booking policy",
    description="Safe tool-use rules for finding and booking CityCare appointments.",
    mime_type="text/markdown",
)
def appointment_booking_policy() -> str:
    """Provide the model with the booking order and confirmation rule."""
    return """# CityCare appointment booking policy

1. Identify the hospital, doctor, and date requested by the patient.
2. Call `get_available_slots` before proposing a time.
3. Collect the patient's reason, temperature in Fahrenheit, and at least one listed symptom.
4. Call `book_appointment` only after the patient explicitly confirms one returned slot.
5. Never invent availability, medical symptoms, or a confirmation. The CityCare API decides capacity and booking eligibility.
"""


@mcp.prompt(
    name="book_appointment_safely",
    description="Guide a CityCare assistant through an availability check and confirmed appointment booking.",
)
def book_appointment_safely() -> str:
    """Return a reusable prompt that makes the model select the correct tool sequence."""
    return (
        "You are CityCare's appointment assistant. First use search_hospitals and list_hospital_doctors "
        "to determine the hospital and doctor identifiers, then determine the date. "
        "Use get_available_slots to retrieve real availability. Present only returned slots. Before calling "
        "book_appointment, obtain an explicit confirmation of one exact slot and collect a truthful reason, "
        "temperature in Fahrenheit, and at least one symptom. Never ask for or supply a patient ID: booking "
        "identity comes from the authenticated CityCare account. If a field is missing, ask a concise follow-up."
    )


@mcp.tool
async def search_hospitals(
    search: Annotated[
        str,
        Field(description="Hospital, clinic, city, or address text provided by the patient.", min_length=1),
    ],
) -> list[dict]:
    """Find active CityCare hospitals before checking a doctor's availability."""
    return await search_hospitals_from_api(search)


@mcp.tool
async def list_hospital_doctors(
    hospital_id: Annotated[
        str,
        Field(description="24-character CityCare hospital ID returned by search_hospitals.", min_length=24, max_length=24),
    ],
) -> list[dict]:
    """List active doctors at a hospital so the patient can select a doctor profile."""
    return await list_hospital_doctors_from_api(hospital_id)


@mcp.tool
async def get_prescription(
    patient_id: Annotated[str, Field(description="The patient record ID to retrieve.", min_length=1)],
    ctx: Context,
) -> dict:
    """Get prescription evidence only after the server verifies caller authorization."""
    return await get_prescription_for_requester(patient_id, requester_from_mcp_context(ctx))


@mcp.tool
async def search_prescriptions(
    patient_id: Annotated[str, Field(description="The patient record ID to search.", min_length=1)],
    query: Annotated[str, Field(description="Question limited to the patient's prescription records.", min_length=1)],
    ctx: Context,
) -> dict:
    """Search prescription evidence only after the server verifies caller authorization."""
    return await search_prescriptions_for_requester(patient_id, query, requester_from_mcp_context(ctx))


@mcp.tool
async def list_patient_appointments(
    patient_id: Annotated[str, Field(description="The patient record ID whose appointments are requested.", min_length=1)],
    ctx: Context,
) -> dict:
    """List one patient's appointments after the server verifies access."""
    return await list_patient_appointments_for_requester(patient_id, requester_from_mcp_context(ctx))


@mcp.tool
async def get_doctor_schedule(
    appointment_date: Annotated[str, Field(description="Schedule date in YYYY-MM-DD format.", pattern=r"^\d{4}-\d{2}-\d{2}$")],
    ctx: Context,
) -> dict:
    """Get a doctor or hospital-owner scoped schedule for one date."""
    return await get_doctor_schedule_for_requester(appointment_date, requester_from_mcp_context(ctx))


@mcp.tool
async def get_available_slots(
    hospital_id: Annotated[
        str,
        Field(description="24-character CityCare hospital ID selected by the patient.", min_length=24, max_length=24),
    ],
    doctor_id: Annotated[
        str,
        Field(description="24-character doctor profile ID at that hospital.", min_length=24, max_length=24),
    ],
    appointment_date: Annotated[
        str,
        Field(description="Requested appointment date in YYYY-MM-DD format.", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    ],
) -> dict:
    """Get real slots for one doctor and date before proposing or booking any appointment."""
    return await get_available_slots_from_api(hospital_id, doctor_id, appointment_date)


@mcp.tool
async def book_appointment(
    hospital_id: Annotated[
        str,
        Field(description="24-character CityCare hospital ID already chosen by the patient.", min_length=24, max_length=24),
    ],
    doctor_id: Annotated[
        str,
        Field(description="24-character doctor profile ID already chosen by the patient.", min_length=24, max_length=24),
    ],
    appointment_date: Annotated[
        str,
        Field(description="Confirmed appointment date in YYYY-MM-DD format.", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    ],
    slot: Annotated[
        str,
        Field(description="Exact available HH:MM slot returned by get_available_slots and explicitly confirmed by the patient."),
    ],
    reason: Annotated[
        str,
        Field(description="Patient-provided reason for visit; at least 10 characters. Do not invent medical details.", min_length=10),
    ],
    temperature: Annotated[
        float,
        Field(description="Patient-provided body temperature in Fahrenheit.", ge=95.0, le=110.0),
    ],
    symptoms: Annotated[
        list[str],
        Field(description="At least one patient-reported symptom accepted by CityCare, for example fever or cough.", min_length=1),
    ],
    ctx: Context,
) -> dict:
    """Create one confirmed appointment for the authenticated patient; never call without explicit consent."""
    requester = requester_from_mcp_context(ctx)
    if requester.role != "patient":
        raise MCPAuthorizationError("Only a patient account may book an appointment through this tool.")

    return await book_appointment_via_api(
        hospital_id=hospital_id,
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        slot=slot,
        reason=reason,
        temperature=temperature,
        symptoms=symptoms,
        authorization=authorization_header_from_mcp_context(ctx),
    )


# Uvicorn entry point for the final Streamable HTTP transport. The same FastMCP
# definitions remain unchanged; only the client connection mechanism changes.
app = mcp.http_app(path="/mcp", transport="streamable-http")


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport=transport,
            host=os.getenv("MCP_HOST", "127.0.0.1"),
            port=int(os.getenv("MCP_PORT", "8001")),
        )
