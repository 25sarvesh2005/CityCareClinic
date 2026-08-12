"""Authorized MCP wrappers around existing appointment CRUD functions."""

from __future__ import annotations

import os
from typing import Any

import httpx

from core.constants import UserRole
from core.cruds.appointment_crud import find_all_appointments_by_patient, find_schedule_by_date
from core.database.database import get_engine
from core.models.appointment_model import AppointmentModel
from mcp_server.tools.auth import RequesterContext, authorize_patient_access, authorized_doctor_ids


class CityCareApiError(RuntimeError):
    """A safe, user-facing error returned by the CityCare HTTP API wrapper."""


def _citycare_api_base_url() -> str:
    """Return the CityCare application origin; versioned routes begin with /api."""
    return os.getenv("CITYCARE_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


async def _citycare_api_request(
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    authorization: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Call CityCare's API without recreating appointment business rules in MCP."""
    headers = {"Authorization": authorization} if authorization else {}

    async def request_with(active_client: httpx.AsyncClient) -> dict[str, Any]:
        try:
            response = await active_client.request(
                method,
                path,
                params=params,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            detail = "CityCare could not complete this request."
            try:
                body = error.response.json()
                if isinstance(body, dict) and isinstance(body.get("detail"), str):
                    detail = body["detail"]
            except ValueError:
                pass
            raise CityCareApiError(detail) from error
        except httpx.HTTPError as error:
            raise CityCareApiError("CityCare's appointment service is unavailable. Please try again later.") from error

        body = response.json()
        if not isinstance(body, dict):
            raise CityCareApiError("CityCare returned an unexpected appointment response.")
        return body

    if client is not None:
        return await request_with(client)

    async with httpx.AsyncClient(base_url=_citycare_api_base_url(), timeout=10.0) as active_client:
        return await request_with(active_client)


async def get_available_slots_from_api(
    hospital_id: str,
    doctor_id: str,
    appointment_date: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Read doctor-specific availability from the existing Day-4 CityCare API."""
    return await _citycare_api_request(
        "GET",
        f"/api/v1/hospitals/{hospital_id}/doctors/{doctor_id}/free-slots",
        params={"date": appointment_date},
        client=client,
    )


async def search_hospitals_from_api(
    search: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Find active CityCare hospitals by a patient-provided name or location."""
    headers: dict[str, str] = {}

    async def request_with(active_client: httpx.AsyncClient) -> list[dict[str, Any]]:
        try:
            response = await active_client.get("/api/v1/hospitals", params={"search": search}, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise CityCareApiError("CityCare could not find matching hospitals.") from error
        except httpx.HTTPError as error:
            raise CityCareApiError("CityCare's appointment service is unavailable. Please try again later.") from error

        body = response.json()
        if not isinstance(body, list) or not all(isinstance(item, dict) for item in body):
            raise CityCareApiError("CityCare returned an unexpected hospital search response.")
        return body

    if client is not None:
        return await request_with(client)
    async with httpx.AsyncClient(base_url=_citycare_api_base_url(), timeout=10.0) as active_client:
        return await request_with(active_client)


async def list_hospital_doctors_from_api(
    hospital_id: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """List active doctor profiles at a patient-selected CityCare hospital."""
    async def request_with(active_client: httpx.AsyncClient) -> list[dict[str, Any]]:
        try:
            response = await active_client.get(f"/api/v1/hospitals/{hospital_id}/doctors")
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise CityCareApiError("CityCare could not find doctors at that hospital.") from error
        except httpx.HTTPError as error:
            raise CityCareApiError("CityCare's appointment service is unavailable. Please try again later.") from error

        body = response.json()
        if not isinstance(body, list) or not all(isinstance(item, dict) for item in body):
            raise CityCareApiError("CityCare returned an unexpected doctor list response.")
        return body

    if client is not None:
        return await request_with(client)
    async with httpx.AsyncClient(base_url=_citycare_api_base_url(), timeout=10.0) as active_client:
        return await request_with(active_client)


async def book_appointment_via_api(
    *,
    hospital_id: str,
    doctor_id: str,
    appointment_date: str,
    slot: str,
    reason: str,
    temperature: float,
    symptoms: list[str],
    authorization: str,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Book only for the patient encoded in the verified CityCare JWT."""
    return await _citycare_api_request(
        "POST",
        "/api/v1/book",
        authorization=authorization,
        payload={
            "hospital_id": hospital_id,
            "doctor_id": doctor_id,
            "date": appointment_date,
            "slot": slot,
            "reason": reason,
            "temperature": temperature,
            "symptoms": symptoms,
        },
        client=client,
    )


def _serialize_appointment(appointment: AppointmentModel) -> dict[str, Any]:
    return {
        "appointment_id": str(appointment.id),
        "doctor_id": appointment.doctor_id,
        "patient_id": appointment.patient_id,
        "patient_name": appointment.patient_name,
        "date": appointment.date,
        "slot": appointment.slot,
        "status": appointment.status.value,
        "is_cancelled": appointment.is_cancelled,
    }


async def list_patient_appointments_for_requester(
    patient_id: str, requester: RequesterContext, engine=None
) -> dict[str, Any]:
    """List only appointments the caller is authorized to see."""
    active_engine = engine or get_engine()
    await authorize_patient_access(active_engine, requester, patient_id)

    if requester.role == UserRole.PATIENT.value:
        appointments = await find_all_appointments_by_patient(active_engine, patient_id)
    elif requester.role == UserRole.HOSPITAL_OWNER.value:
        appointments = await active_engine.find(
            AppointmentModel,
            (AppointmentModel.hospital_id == requester.hospital_id)
            & (AppointmentModel.patient_id == patient_id),
        )
    else:
        doctor_ids = await authorized_doctor_ids(active_engine, requester)
        appointments = await active_engine.find(
            AppointmentModel,
            (AppointmentModel.hospital_id == requester.hospital_id)
            & (AppointmentModel.patient_id == patient_id)
            & (AppointmentModel.doctor_id.in_(list(doctor_ids))),
        )

    return {"patient_id": patient_id, "appointments": [_serialize_appointment(item) for item in appointments]}


async def get_doctor_schedule_for_requester(
    appointment_date: str, requester: RequesterContext, engine=None
) -> dict[str, Any]:
    """Return the caller's hospital-scoped doctor schedule for one date."""
    active_engine = engine or get_engine()
    doctor_ids = await authorized_doctor_ids(active_engine, requester)
    appointments = await find_schedule_by_date(
        active_engine,
        requester.hospital_id or "",
        appointment_date,
        doctor_ids=list(doctor_ids),
    )
    return {"date": appointment_date, "appointments": [_serialize_appointment(item) for item in appointments]}
