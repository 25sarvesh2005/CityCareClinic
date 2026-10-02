"""Authentication and authorization helpers for MCP tool calls."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Context

# This service runs outside the FastAPI application's lifespan, so load the
# project configuration before importing the JWT helper.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from chatbot.tools import get_authorized_doctor_ids
from common.auth import decode_jwt
from core.constants import UserRole
from core.models.appointment_model import AppointmentModel


class MCPAuthorizationError(PermissionError):
    """Raised before protected clinic data is read by an MCP tool."""


@dataclass(frozen=True)
class RequesterContext:
    """Identity claims verified from the MCP HTTP Authorization header."""

    user_id: str
    role: str
    hospital_id: str | None
    email: str | None = None

    def as_claims(self) -> dict[str, str | None]:
        return {
            "user_id": self.user_id,
            "role": self.role,
            "hospital_id": self.hospital_id,
            "email": self.email,
        }


def requester_from_authorization_header(authorization: str | None) -> RequesterContext:
    """Validate a CityCare JWT from a Bearer header and return its trusted claims."""
    if not authorization or not authorization.startswith("Bearer "):
        raise MCPAuthorizationError("A valid Bearer token is required.")

    token = authorization.removeprefix("Bearer ").strip()
    claims = decode_jwt(token)
    if not claims:
        raise MCPAuthorizationError("The access token is invalid or expired.")

    user_id = claims.get("user_id")
    role = claims.get("role")
    valid_roles = {item.value for item in UserRole}
    if not isinstance(user_id, str) or not user_id or role not in valid_roles:
        raise MCPAuthorizationError("The access token is missing required identity claims.")

    hospital_id = claims.get("hospital_id")
    if hospital_id is not None and not isinstance(hospital_id, str):
        raise MCPAuthorizationError("The access token has an invalid hospital scope.")

    return RequesterContext(
        user_id=user_id,
        role=role,
        hospital_id=hospital_id,
        email=claims.get("email") if isinstance(claims.get("email"), str) else None,
    )


def authorization_header_from_mcp_context(ctx: Context) -> str:
    """Return the authenticated request header, with a local stdio-only fallback."""
    request_context = ctx.request_context
    request = request_context.request if request_context else None
    if request is not None:
        authorization = request.headers.get("authorization")
        if authorization:
            return authorization
        raise MCPAuthorizationError("A valid Bearer token is required.")

    # Codex's local stdio transport has no HTTP request object. This
    # development-only token is intentionally opt-in and must never be used to
    # make an unauthenticated HTTP deployment public.
    local_token = os.getenv("CITYCARE_MCP_JWT", "").strip()
    if local_token:
        return f"Bearer {local_token}"
    raise MCPAuthorizationError(
        "A valid Bearer token is required. For local stdio development, set CITYCARE_MCP_JWT."
    )


def requester_from_mcp_context(ctx: Context) -> RequesterContext:
    """Resolve trusted identity claims; never trust a patient ID supplied by a model."""
    return requester_from_authorization_header(authorization_header_from_mcp_context(ctx))


async def authorize_patient_access(engine, requester: RequesterContext, patient_id: str) -> None:
    """Prove the requester may access one patient's records before retrieval."""
    if not patient_id:
        raise MCPAuthorizationError("A patient ID is required.")

    if requester.role == UserRole.PATIENT.value:
        if requester.user_id != patient_id:
            raise MCPAuthorizationError("Patients may access only their own records.")
        return

    if requester.role == UserRole.DOCTOR.value:
        if not requester.hospital_id:
            raise MCPAuthorizationError("Doctor token is missing its hospital scope.")
        doctor_ids = await get_authorized_doctor_ids(engine, requester.as_claims())
        if not doctor_ids:
            raise MCPAuthorizationError("No authorized doctor profile was found.")
        appointment = await engine.find_one(
            AppointmentModel,
            (AppointmentModel.hospital_id == requester.hospital_id)
            & (AppointmentModel.patient_id == patient_id)
            & (AppointmentModel.doctor_id.in_(list(doctor_ids))),
        )
        if appointment is None:
            raise MCPAuthorizationError("You are not authorized to access this patient's records.")
        return

    if requester.role == UserRole.HOSPITAL_OWNER.value:
        if not requester.hospital_id:
            raise MCPAuthorizationError("Hospital-owner token is missing its hospital scope.")
        appointment = await engine.find_one(
            AppointmentModel,
            (AppointmentModel.hospital_id == requester.hospital_id)
            & (AppointmentModel.patient_id == patient_id),
        )
        if appointment is None:
            raise MCPAuthorizationError("You are not authorized to access this patient's records.")
        return

    raise MCPAuthorizationError("This role is not permitted to access patient records through MCP.")


async def authorized_doctor_ids(engine, requester: RequesterContext) -> set[str]:
    """Return the caller's permitted doctor IDs after enforcing a tenant scope."""
    if requester.role not in {UserRole.DOCTOR.value, UserRole.HOSPITAL_OWNER.value}:
        raise MCPAuthorizationError("Only doctors and hospital owners may view doctor schedules.")
    if not requester.hospital_id:
        raise MCPAuthorizationError("This token is missing its hospital scope.")
    return await get_authorized_doctor_ids(engine, requester.as_claims())
