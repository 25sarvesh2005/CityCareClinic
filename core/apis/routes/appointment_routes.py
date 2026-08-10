import logging
from datetime import date as date_type
from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from common.auth import decodeJWT, get_current_user, oauth2_scheme
from core.apis.schemas.appointment_schema import (
    AppointmentResponse,
    BookAppointmentRequest,
    CancelResponse,
)
from core.apis.schemas.discovery_schema import (
    DoctorDiscoveryResponse,
    DoctorFreeSlotsResponse,
    HospitalDiscoveryResponse,
)
from core.apis.schemas.doctor_schema import (
    DoctorInfoResponse,
    FreeSlotsResponse,
)
from core.constants import MAX_BOOKING_DAYS, calculate_free_slots
from core.controllers.appointment_controller import AppointmentController
from core.controllers.doctor_controller import DoctorController
from core.cruds.appointment_crud import find_booked_slots_by_date
from core.cruds.doctor_profile_crud import find_profile_by_id, find_profiles_by_hospital
from core.cruds.hospital_crud import find_all_hospitals, find_hospital_by_id
from core.database.database import get_engine

router = APIRouter(tags=["Appointments & Clinic"])


# ─── Discovery Endpoints (Patient-Facing) ────────────────────────────────────


@router.get(
    "/v1/hospitals",
    response_model=List[HospitalDiscoveryResponse],
    status_code=status.HTTP_200_OK,
    summary="List all active hospitals on the platform",
)
async def list_hospitals(
    city: str = Query(default=None, description="Filter by city name or search term."),
    search: str = Query(default=None, description="Filter by hospital name, city, or address.")
) -> List[HospitalDiscoveryResponse]:
    """
    List all active, approved hospitals available for patient booking.

    Optionally filter by hospital name, city, or address. This endpoint is public — no auth required.

    Args:
        city (str, optional): City name or query filter.
        search (str, optional): Search term for hospital name, city, or address.

    Returns:
        List[HospitalDiscoveryResponse]: Active hospitals on the platform.
    """
    try:
        engine = get_engine()
        hospitals = await find_all_hospitals(engine)
        q = (search or city or "").strip()
        results = [
            HospitalDiscoveryResponse(
                hospital_id=str(h.id),
                name=h.name,
                city=h.city,
                address=h.address,
                contact_number=h.contact_number,
                is_active=h.is_active,
            )
            for h in hospitals
            if h.is_active and h.is_approved
            and (
                not q
                or q.lower() in h.name.lower()
                or q.lower() in h.city.lower()
                or q.lower() in h.address.lower()
            )
        ]
        return results
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to list hospitals: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/hospitals/{hospital_id}/doctors",
    response_model=List[DoctorDiscoveryResponse],
    status_code=status.HTTP_200_OK,
    summary="List doctors at a specific hospital",
)
async def list_hospital_doctors(
    hospital_id: str,
) -> List[DoctorDiscoveryResponse]:
    """
    List all active doctor profiles at a specific hospital.

    Args:
        hospital_id (str): Hospital ObjectId from GET /api/v1/hospitals.

    Returns:
        List[DoctorDiscoveryResponse]: Active doctor profiles at this hospital.

    Raises:
        HTTPException 404: Hospital not found.
    """
    try:
        engine = get_engine()
        hospital = await find_hospital_by_id(engine, hospital_id)
        if not hospital:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hospital '{hospital_id}' not found.",
            )
        profiles = await find_profiles_by_hospital(engine, hospital_id)
        active_profiles = [p for p in profiles if p.is_active]

        from bson import ObjectId
        from core.models.user_model import UserModel

        user_ids = []
        for p in active_profiles:
            if p.user_id:
                try:
                    user_ids.append(ObjectId(p.user_id))
                except Exception:
                    pass

        users = await engine.find(UserModel, UserModel.id.in_(user_ids)) if user_ids else []
        users_map = {str(u.id): u for u in users}

        return [
            DoctorDiscoveryResponse(
                profile_id=str(p.id),
                user_id=p.user_id,
                name=users_map[p.user_id].name if p.user_id in users_map else "Doctor",
                email=users_map[p.user_id].email if p.user_id in users_map else "",
                specialization=p.specialization,
                consultation_fee=p.consultation_fee,
                clinic_hours=p.clinic_hours,
                languages_spoken=p.languages_spoken,
                unavailable_dates=p.unavailable_dates or [],
                is_active=p.is_active,
            )
            for p in active_profiles
        ]
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to list hospital doctors: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/hospitals/{hospital_id}/doctors/{doctor_id}/free-slots",
    response_model=DoctorFreeSlotsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get free appointment slots for a specific doctor",
)
async def get_doctor_free_slots(
    hospital_id: str,
    doctor_id: str,
    date: str = Query(..., description="Date in YYYY-MM-DD format."),
) -> DoctorFreeSlotsResponse:
    """
    Return available (un-booked) appointment slots for a specific doctor
    at a specific hospital on a given date.

    Args:
        hospital_id (str): Hospital ObjectId.
        doctor_id   (str): Doctor profile ObjectId (profile_id from list doctors).
        date        (str): Date in YYYY-MM-DD format.

    Returns:
        DoctorFreeSlotsResponse: Available slots for this doctor on this date.

    Raises:
        HTTPException 400: Invalid or out-of-range date.
        HTTPException 404: Hospital or doctor profile not found.
    """
    try:
        engine = get_engine()

        # Validate date
        try:
            query_date = date_type.fromisoformat(date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD.",
            )

        today = date_type.today()
        if query_date < today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot query slots for a past date.",
            )
        if query_date > today + timedelta(days=MAX_BOOKING_DAYS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Slots can only be viewed up to {MAX_BOOKING_DAYS} days in advance.",
            )

        # Validate hospital exists
        hospital = await find_hospital_by_id(engine, hospital_id)
        if not hospital or not hospital.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hospital not found or not active.",
            )

        # Validate doctor profile exists at this hospital
        profile = await find_profile_by_id(engine, hospital_id, doctor_id)
        if not profile or not profile.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found at this hospital or not active.",
            )

        is_unavailable = date in (profile.unavailable_dates or [])
        if is_unavailable:
            free_slots = []
        else:
            booked_slots = await find_booked_slots_by_date(engine, hospital_id, doctor_id, date)
            free_slots = calculate_free_slots(booked_slots)

        return DoctorFreeSlotsResponse(
            hospital_id=hospital_id,
            doctor_id=doctor_id,
            date=date,
            available_slots=free_slots,
            total_available=len(free_slots),
            is_unavailable=is_unavailable,
        )
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to get doctor free slots: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


# ─── Legacy Single-Clinic Endpoints ──────────────────────────────────────────
# These pre-date multi-tenancy and remain for backward compatibility.
# They will be deprecated in a future phase once the frontend migrates.


@router.get(
    "/v1/doctor-info",
    response_model=DoctorInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="[Legacy] Get clinic and doctor profile",
)
async def get_doctor_info() -> DoctorInfoResponse:
    """
    Retrieve static profile information about the clinic and doctor.

    Returns:
        DoctorInfoResponse: Doctor name, fee, timings, languages spoken, and address.

    Raises:
        HTTPException:
            * ``500 Internal Server Error`` — any unexpected failure.
    """
    try:
        logging.info("Calling GET /v1/doctor-info endpoint")
        result = await DoctorController().get_doctor_info()
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to retrieve doctor info: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/free-slots",
    response_model=FreeSlotsResponse,
    status_code=status.HTTP_200_OK,
    summary="[Legacy] Get available appointment slots for a date",
)
async def get_free_slots(
    date: str = Query(..., description="Appointment date in YYYY-MM-DD format.")
) -> FreeSlotsResponse:
    """
    List available appointment slots for the given date.

    Args:
        date: Date in YYYY-MM-DD format (must be between today and +7 days).

    Returns:
        FreeSlotsResponse: Date, list of unbooked slot strings, and count.

    Raises:
        HTTPException:
            * ``400 Bad Request`` — invalid date format or out-of-bounds date.
            * ``500 Internal Server Error`` — any unexpected failure.
    """
    try:
        logging.info("Calling GET /v1/free-slots endpoint for date: %s", date)
        result = await DoctorController().get_free_slots(requested_date=date)
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error(
            "Failed to fetch free slots for date '%s': %s",
            date,
            str(error),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.post(
    "/v1/book",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book an appointment",
)
async def book_appointment(
    booking_request: BookAppointmentRequest,
    token: str = Depends(oauth2_scheme),
) -> AppointmentResponse:
    """
    Book an appointment slot for the currently authenticated patient.

    Args:
        booking_request: Validated appointment payload. FastAPI rejects malformed bodies
            with ``422`` before this function is entered.
        token: JWT token obtained from the login endpoint. FastAPI extracts it
            from the ``Authorization`` header and passes it to this function.

    Returns:
        AppointmentResponse: Saved appointment document details.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``400 Bad Request`` — invalid date format, out-of-range date, or invalid slot.
            * ``409 Conflict`` — slot is already booked or patient has existing appointment for date.
            * ``500 Internal Server Error`` — any unexpected failure.
    """
    try:
        logging.info("Calling POST /v1/book endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning("Invalid or expired token provided for appointment booking")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        # `await` is required: book_appointment is an async function, so calling it
        # without awaiting hands back a coroutine object rather than the result.
        result = await AppointmentController().book_appointment(
            booking_request=booking_request,
            authenticated_user_details=authenticated_user_details,
        )
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to book appointment: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/my-appointments",
    response_model=List[AppointmentResponse],
    status_code=status.HTTP_200_OK,
    summary="List my appointments",
)
async def list_my_appointments(
    token: str = Depends(oauth2_scheme),
) -> List[AppointmentResponse]:
    """
    List all appointments (active and cancelled) for the authenticated patient.

    Args:
        token: JWT token obtained from the login endpoint. FastAPI extracts it
            from the ``Authorization`` header and passes it to this function.

    Returns:
        List[AppointmentResponse]: List of appointment records.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``500 Internal Server Error`` — any unexpected failure.
    """
    try:
        logging.info("Calling GET /v1/my-appointments endpoint")
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning(
                "Invalid or expired token provided for listing appointments"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        result = await AppointmentController().list_my_appointments(
            authenticated_user_details=authenticated_user_details
        )
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to list appointments: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.delete(
    "/v1/cancel/{appointment_id}",
    response_model=CancelResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel an appointment",
)
async def cancel_appointment(
    appointment_id: str,
    token: str = Depends(oauth2_scheme),
) -> CancelResponse:
    """
    Soft-delete an appointment belonging to the authenticated patient.

    Args:
        appointment_id: ObjectId of the appointment to cancel.
        token: JWT token obtained from the login endpoint. FastAPI extracts it
            from the ``Authorization`` header and passes it to this function.

    Returns:
        CancelResponse: Confirmation message freeing the slot.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — the token is missing, forged, or expired.
            * ``404 Not Found`` — appointment not found or owned by another patient.
            * ``409 Conflict`` — appointment is already cancelled.
            * ``500 Internal Server Error`` — any unexpected failure.
    """
    try:
        logging.info("Calling DELETE /v1/cancel/%s endpoint", appointment_id)
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            logging.warning(
                "Invalid or expired token provided for appointment cancellation"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        result = await AppointmentController().cancel_appointment(
            appointment_id=appointment_id,
            authenticated_user_details=authenticated_user_details,
        )
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error(
            "Failed to cancel appointment '%s': %s",
            appointment_id,
            str(error),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )
