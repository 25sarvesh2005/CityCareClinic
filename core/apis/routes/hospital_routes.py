"""
─────────────────────────────────────────────────────────────────────────────
File        : core/apis/routes/hospital_routes.py
Purpose     : HTTP route handlers for hospital-owner doctor management.

Endpoints:
    POST  /api/v1/hospital/doctors
        Create a new doctor under the calling owner's hospital.

    GET   /api/v1/hospital/doctors
        List all doctors in the calling owner's hospital.

    PATCH /api/v1/hospital/doctors/{profile_id}/status
        Activate or deactivate a doctor profile.

Auth & Scoping:
    All routes depend on get_hospital_scope() which:
      1. Validates the Bearer token (401 if invalid).
      2. Enforces role == HOSPITAL_OWNER or DOCTOR has a non-null hospital_id
         in their JWT (403 if missing).

    The scope dict passed to the controller carries the hospital_id from
    the JWT — controllers NEVER read hospital_id from the request body.

Used By:
    - core/apis/api.py (registered as hospital_router)
─────────────────────────────────────────────────────────────────────────────
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from common.auth import require_super_admin
from common.tenant_scope import get_hospital_scope
from core.apis.schemas.admin_schema import HospitalStatsResponse
from core.apis.schemas.hospital_schema import (
    CreateDoctorRequest,
    DoctorListEntryResponse,
    DoctorProfileResponse,
    SetDoctorStatusRequest,
)
from core.controllers.admin_controller import AdminController
from core.controllers.hospital_controller import HospitalController

router = APIRouter(tags=["Hospital Owner"])


def _require_owner_role(scope: dict = Depends(get_hospital_scope)) -> dict:
    """
    Inline dependency: ensures the caller is a HOSPITAL_OWNER.

    get_hospital_scope() already guarantees a valid token and non-null
    hospital_id for scoped roles. This adds the role=hospital_owner check.

    Args:
        scope (dict): JWT payload injected by get_hospital_scope.

    Returns:
        dict: The same scope payload if role is hospital_owner.

    Raises:
        HTTPException 403: If the role is not hospital_owner.
    """
    if scope.get("role") != "hospital_owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Hospital owner role required.",
        )
    return scope


@router.post(
    "/v1/hospital/doctors",
    response_model=DoctorProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a doctor under the calling owner's hospital",
)
async def create_doctor(
    request: CreateDoctorRequest,
    scope: dict = Depends(_require_owner_role),
) -> DoctorProfileResponse:
    """
    Provision a DOCTOR user account and bind it to the calling owner's hospital.

    The hospital_id is derived exclusively from the caller's JWT — it cannot
    be overridden via the request body (the schema has no hospital_id field).

    Args:
        request (CreateDoctorRequest): Doctor account and profile details.
        scope   (dict)               : JWT scope injected by _require_owner_role.

    Returns:
        DoctorProfileResponse: The created doctor user and profile.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — missing or invalid token.
            * ``403 Forbidden``    — not a hospital_owner, or hospital is suspended.
            * ``409 Conflict``     — email already registered.
            * ``500 Internal``     — unexpected failure.
    """
    try:
        logging.info(
            "POST /v1/hospital/doctors called by owner: %s (hospital: %s)",
            scope.get("email"),
            scope.get("hospital_id"),
        )
        result = await HospitalController().create_doctor(
            request=request, scope=scope
        )
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to create doctor: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/hospital/doctors",
    response_model=List[DoctorListEntryResponse],
    status_code=status.HTTP_200_OK,
    summary="List all doctors in the calling owner's hospital",
)
async def list_doctors(
    scope: dict = Depends(_require_owner_role),
) -> List[DoctorListEntryResponse]:
    """
    Retrieve all doctor profiles scoped to the calling owner's hospital.

    The owner cannot list doctors from any other hospital regardless of
    what is passed in the request — scope is entirely JWT-derived.

    Args:
        scope (dict): JWT scope injected by _require_owner_role.

    Returns:
        List[DoctorListEntryResponse]: All doctor profiles for this hospital.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — missing or invalid token.
            * ``403 Forbidden``    — not a hospital_owner.
            * ``500 Internal``     — unexpected failure.
    """
    try:
        logging.info(
            "GET /v1/hospital/doctors called by owner: %s (hospital: %s)",
            scope.get("email"),
            scope.get("hospital_id"),
        )
        result = await HospitalController().list_doctors(scope=scope)
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to list doctors: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.patch(
    "/v1/hospital/doctors/{profile_id}/status",
    response_model=DoctorProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate or deactivate a doctor profile",
)
async def set_doctor_status(
    profile_id: str,
    request: SetDoctorStatusRequest,
    scope: dict = Depends(_require_owner_role),
) -> DoctorProfileResponse:
    """
    Toggle is_active on a doctor profile within the calling owner's hospital.

    The profile lookup is scoped by hospital_id from the JWT — an owner
    cannot modify profiles belonging to a different hospital.

    Args:
        profile_id (str)                 : String ObjectId of the profile (path param).
        request    (SetDoctorStatusRequest): Contains is_active flag.
        scope      (dict)                : JWT scope injected by _require_owner_role.

    Returns:
        DoctorProfileResponse: The updated profile.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — missing or invalid token.
            * ``403 Forbidden``    — not a hospital_owner.
            * ``404 Not Found``    — profile not found within this hospital.
            * ``500 Internal``     — unexpected failure.
    """
    try:
        logging.info(
            "PATCH /v1/hospital/doctors/%s/status called by owner: %s (hospital: %s)",
            profile_id,
            scope.get("email"),
            scope.get("hospital_id"),
        )
        result = await HospitalController().set_doctor_status(
            profile_id=profile_id, request=request, scope=scope
        )
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error(
            "Failed to set doctor status for profile '%s': %s",
            profile_id,
            str(error),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/hospital/stats",
    response_model=HospitalStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get hospital stats (scoped to calling owner's hospital)",
)
async def get_hospital_stats_owner(
    scope: dict = Depends(_require_owner_role),
) -> HospitalStatsResponse:
    """
    Retrieve statistics for the calling owner's hospital.

    Hospital ID is extracted exclusively from the JWT scope via get_hospital_scope.
    Delegates to AdminController().get_hospital_stats(hospital_id).

    Args:
        scope (dict): JWT scope injected by _require_owner_role.

    Returns:
        HospitalStatsResponse: Hospital metrics.
    """
    try:
        hospital_id = scope["hospital_id"]
        logging.info(
            "GET /v1/hospital/stats called by owner: %s (hospital: %s)",
            scope.get("email"),
            hospital_id,
        )
        result = await AdminController().get_hospital_stats(hospital_id=hospital_id)
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to fetch hospital owner stats: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )

