import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from common.auth import decodeJWT, decode_jwt, oauth2_scheme
from core.apis.schemas.doctor_schema import (
    DoctorScheduleResponse,
    DoctorStatsResponse,
    DoctorUnavailabilityRequest,
    DoctorUnavailabilityResponse,
)
from core.controllers.doctor_controller import DoctorController

router = APIRouter(tags=["Doctor Dashboard"])


@router.get(
    "/v1/doctor/schedule",
    response_model=DoctorScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get doctor's schedule for a specific date",
)
async def get_doctor_schedule(
    date: str = Query(..., description="Schedule date in YYYY-MM-DD format."),
    token: str = Depends(oauth2_scheme),
) -> DoctorScheduleResponse:
    """
    Retrieve full clinic schedule for a date (Doctor role required).

    Args:
        date: Date in YYYY-MM-DD format.
        token: JWT token obtained from the login endpoint. FastAPI extracts it
            from the ``Authorization`` header and passes it to this function.

    Returns:
        DoctorScheduleResponse: Scheduled and cancelled appointment entries.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``403 Forbidden`` — authenticated user is not a doctor.
            * ``500 Internal Server Error`` — any unexpected failure.
    """
    try:
        logging.info("Calling GET /v1/doctor/schedule endpoint for date: %s", date)
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for doctor schedule")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        if authenticated_user_details.get("role") != "doctor":
            logging.warning("Access denied — non-doctor requested doctor schedule")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Doctor role required.",
            )
        hospital_id = authenticated_user_details.get("hospital_id") or ""
        doctor_user_id = authenticated_user_details.get("user_id") or ""
        result = await DoctorController().get_schedule(
            requested_date=date, hospital_id=hospital_id, doctor_user_id=doctor_user_id
        )
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to fetch doctor schedule: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/doctor/unavailability",
    response_model=DoctorUnavailabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Get doctor's unavailable dates",
)
async def get_doctor_unavailability(
    token: str = Depends(oauth2_scheme),
) -> DoctorUnavailabilityResponse:
    """Retrieve full list of unavailable dates for the doctor (Doctor role required)."""
    try:
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        if authenticated_user_details.get("role") != "doctor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Doctor role required.",
            )
        doctor_user_id = authenticated_user_details.get("user_id") or ""
        hospital_id = authenticated_user_details.get("hospital_id") or ""
        return await DoctorController().get_unavailability_list(
            doctor_user_id=doctor_user_id, hospital_id=hospital_id
        )
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to fetch doctor unavailability: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.post(
    "/v1/doctor/unavailability",
    response_model=DoctorUnavailabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark or unmark a day as unavailable (off-day)",
)
async def toggle_doctor_unavailability(
    payload: DoctorUnavailabilityRequest,
    token: str = Depends(oauth2_scheme),
) -> DoctorUnavailabilityResponse:
    """
    Mark or unmark a date as unavailable.

    If marking unavailable, any existing active appointments for that date are auto-cancelled
    and a reschedule notice is attached.
    """
    try:
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        if authenticated_user_details.get("role") != "doctor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Doctor role required.",
            )
        doctor_user_id = authenticated_user_details.get("user_id") or ""
        hospital_id = authenticated_user_details.get("hospital_id") or ""
        return await DoctorController().toggle_unavailability(
            doctor_user_id=doctor_user_id, hospital_id=hospital_id, payload=payload
        )
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to update doctor unavailability: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/doctor/stats",
    response_model=DoctorStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get clinic statistics",
)
async def get_doctor_stats(
    token: str = Depends(oauth2_scheme),
) -> DoctorStatsResponse:
    """
    Retrieve clinic statistics (Doctor role required).

    Args:
        token: JWT token obtained from the login endpoint. FastAPI extracts it
            from the ``Authorization`` header and passes it to this function.

    Returns:
        DoctorStatsResponse: Registered patient count, today's visit count, upcoming visits.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``403 Forbidden`` — authenticated user is not a doctor.
            * ``500 Internal Server Error`` — any unexpected failure.
    """
    try:
        logging.info("Calling GET /v1/doctor/stats endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for doctor stats")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        if authenticated_user_details.get("role") != "doctor":
            logging.warning("Access denied — non-doctor requested doctor stats")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Doctor role required.",
            )
        hospital_id = authenticated_user_details.get("hospital_id") or ""
        result = await DoctorController().get_stats(hospital_id=hospital_id)
        return result

    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to fetch doctor stats: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )
