"""
─────────────────────────────────────────────────────────────────────────────
File        : core/apis/routes/admin_routes.py
Purpose     : HTTP route handlers for super-admin hospital management.

Endpoints:
    POST  /api/v1/admin/hospitals
        Register a new hospital tenant (SUPER_ADMIN only).

    POST  /api/v1/admin/hospitals/{hospital_id}/owner
        Create a HOSPITAL_OWNER user and bind it to the hospital.

    PATCH /api/v1/admin/hospitals/{hospital_id}/status
        Toggle is_active / is_approved on a hospital.

    GET   /api/v1/admin/hospitals
        List all hospitals on the platform (super-admin dashboard).

Auth:
    All routes require role == super_admin, enforced via the
    require_super_admin dependency from common/auth.py.

Used By:
    - core/apis/api.py (registered as admin_router)
─────────────────────────────────────────────────────────────────────────────
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from common.auth import require_super_admin
from core.apis.schemas.admin_schema import (
    CreateHospitalOwnerRequest,
    CreateHospitalRequest,
    HospitalListResponse,
    HospitalOwnerResponse,
    HospitalResponse,
    HospitalStatsResponse,
    PlatformStatsResponse,
    SetHospitalStatusRequest,
)
from core.controllers.admin_controller import AdminController

router = APIRouter(tags=["Super Admin"])


@router.post(
    "/v1/admin/hospitals",
    response_model=HospitalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new hospital tenant",
)
async def create_hospital(
    request: CreateHospitalRequest,
    admin_user: dict = Depends(require_super_admin),
) -> HospitalResponse:
    """
    Register a new hospital/clinic on the platform.

    The hospital starts unapproved and without an owner. Use
    POST /v1/admin/hospitals/{id}/owner to assign an owner, and
    PATCH /v1/admin/hospitals/{id}/status to approve it for live operation.

    Args:
        request    (CreateHospitalRequest): Hospital details.
        admin_user (dict)                 : Injected by require_super_admin.

    Returns:
        HospitalResponse: Persisted hospital document.

    Raises:
        HTTPException:
            * ``403 Forbidden``  — caller is not SUPER_ADMIN.
            * ``409 Conflict``   — hospital name already exists in that city.
            * ``500 Internal``   — unexpected failure.
    """
    try:
        logging.info("POST /v1/admin/hospitals called by: %s", admin_user.get("email"))
        result = await AdminController().create_hospital(
            request=request, admin_user=admin_user
        )
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to create hospital: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.post(
    "/v1/admin/hospitals/{hospital_id}/owner",
    response_model=HospitalOwnerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a hospital owner and bind to hospital",
)
async def create_hospital_owner(
    hospital_id: str,
    request: CreateHospitalOwnerRequest,
    admin_user: dict = Depends(require_super_admin),
) -> HospitalOwnerResponse:
    """
    Create a HOSPITAL_OWNER user account and assign it to the specified hospital.

    Args:
        hospital_id (str)                       : Target hospital ObjectId (path param).
        request     (CreateHospitalOwnerRequest): Owner account details.
        admin_user  (dict)                      : Injected by require_super_admin.

    Returns:
        HospitalOwnerResponse: New owner user details and hospital binding confirmation.

    Raises:
        HTTPException:
            * ``403 Forbidden``  — caller is not SUPER_ADMIN.
            * ``404 Not Found``  — hospital not found.
            * ``409 Conflict``   — email already registered.
            * ``500 Internal``   — unexpected failure.
    """
    try:
        logging.info(
            "POST /v1/admin/hospitals/%s/owner called by: %s",
            hospital_id,
            admin_user.get("email"),
        )
        result = await AdminController().create_hospital_owner(
            hospital_id=hospital_id, request=request, admin_user=admin_user
        )
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error(
            "Failed to create hospital owner for '%s': %s",
            hospital_id,
            str(error),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.patch(
    "/v1/admin/hospitals/{hospital_id}/status",
    response_model=HospitalResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate, suspend, or approve a hospital",
)
async def set_hospital_status(
    hospital_id: str,
    request: SetHospitalStatusRequest,
    admin_user: dict = Depends(require_super_admin),
) -> HospitalResponse:
    """
    Toggle the is_active and/or is_approved flags on a hospital.

    Provide at least one of the two boolean fields. Both may be updated
    in a single call.

    Args:
        hospital_id (str)                   : Target hospital ObjectId (path param).
        request     (SetHospitalStatusRequest): Status flags to update.
        admin_user  (dict)                  : Injected by require_super_admin.

    Returns:
        HospitalResponse: Updated hospital document.

    Raises:
        HTTPException:
            * ``403 Forbidden``             — caller is not SUPER_ADMIN.
            * ``404 Not Found``             — hospital not found.
            * ``422 Unprocessable Entity``  — neither flag provided.
            * ``500 Internal``              — unexpected failure.
    """
    try:
        logging.info(
            "PATCH /v1/admin/hospitals/%s/status called by: %s",
            hospital_id,
            admin_user.get("email"),
        )
        result = await AdminController().set_hospital_status(
            hospital_id=hospital_id, request=request, admin_user=admin_user
        )
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error(
            "Failed to set hospital status for '%s': %s",
            hospital_id,
            str(error),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/admin/hospitals",
    response_model=List[HospitalListResponse],
    status_code=status.HTTP_200_OK,
    summary="List all hospital tenants",
)
async def list_hospitals(
    admin_user: dict = Depends(require_super_admin),
) -> List[HospitalListResponse]:
    """
    Retrieve a summary list of all hospitals on the platform.

    Used by the super-admin dashboard to monitor tenant health and status.

    Args:
        admin_user (dict): Injected by require_super_admin.

    Returns:
        List[HospitalListResponse]: All hospitals, sorted by registration date.

    Raises:
        HTTPException:
            * ``403 Forbidden`` — caller is not SUPER_ADMIN.
            * ``500 Internal``  — unexpected failure.
    """
    try:
        logging.info(
            "GET /v1/admin/hospitals called by: %s", admin_user.get("email")
        )
        result = await AdminController().list_hospitals()
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to list hospitals: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/admin/stats",
    response_model=PlatformStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get platform-wide statistics",
)
async def get_platform_stats(
    admin_user: dict = Depends(require_super_admin),
) -> PlatformStatsResponse:
    """
    Retrieve platform-wide high-level metrics across all hospital tenants.

    Args:
        admin_user (dict): Injected by require_super_admin.

    Returns:
        PlatformStatsResponse: Aggregate platform statistics.
    """
    try:
        logging.info("GET /v1/admin/stats called by: %s", admin_user.get("email"))
        result = await AdminController().get_platform_stats()
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to fetch platform stats: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/admin/hospitals/{hospital_id}/stats",
    response_model=HospitalStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get hospital statistics (unscoped, super admin)",
)
async def get_hospital_stats_admin(
    hospital_id: str,
    admin_user: dict = Depends(require_super_admin),
) -> HospitalStatsResponse:
    """
    Retrieve statistics for any single hospital tenant.

    Args:
        hospital_id (str): Target hospital ObjectId.
        admin_user (dict): Injected by require_super_admin.

    Returns:
        HospitalStatsResponse: Hospital metrics.
    """
    try:
        logging.info(
            "GET /v1/admin/hospitals/%s/stats called by: %s",
            hospital_id,
            admin_user.get("email"),
        )
        result = await AdminController().get_hospital_stats(hospital_id=hospital_id)
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error(
            "Failed to fetch hospital stats for '%s': %s",
            hospital_id,
            str(error),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )

