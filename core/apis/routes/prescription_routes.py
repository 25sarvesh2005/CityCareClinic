"""
─────────────────────────────────────────────────────────────────────────────
File        : core/apis/routes/prescription_routes.py
Purpose     : HTTP Route handlers for prescription creation, status management,
              and PDF viewing/downloading.

Endpoints:
    - PATCH /v1/doctor/appointments/{appointment_id}/accept : Doctor accepts request
    - PATCH /v1/doctor/appointments/{appointment_id}/reject : Doctor rejects request
    - POST  /v1/doctor/prescriptions                         : Doctor creates prescription
    - GET   /v1/patient/prescriptions                        : Patient views prescriptions
    - GET   /v1/patient/prescriptions/{prescription_id}      : View prescription details
    - GET   /v1/patient/prescriptions/{prescription_id}/pdf  : Stream/Download PDF
─────────────────────────────────────────────────────────────────────────────
"""

import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, RedirectResponse

from common.auth import decodeJWT, oauth2_scheme
from core.apis.schemas.prescription_schema import (
    CreatePrescriptionRequest,
    PrescriptionResponse,
    UpdateAppointmentStatusRequest,
)
from core.constants import AppointmentStatus
from core.controllers.prescription_controller import PrescriptionController
from core.services.cloudinary_service import LOCAL_PRESCRIPTION_DIR

router = APIRouter(tags=["Prescriptions & Status Management"])


@router.patch(
    "/v1/doctor/appointments/{appointment_id}/accept",
    status_code=status.HTTP_200_OK,
    summary="Accept a patient appointment request (Doctor role required)",
)
async def accept_appointment_request(
    appointment_id: str,
    token: str = Depends(oauth2_scheme),
) -> dict:
    """Doctor accepts a patient's pending appointment request."""
    try:
        user_details = decodeJWT(token)
        if not user_details:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return await PrescriptionController().update_appointment_status(
            appointment_id=appointment_id,
            new_status=AppointmentStatus.ACCEPTED,
            authenticated_user_details=user_details,
        )
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to accept appointment %s: %s", appointment_id, str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.patch(
    "/v1/doctor/appointments/{appointment_id}/reject",
    status_code=status.HTTP_200_OK,
    summary="Reject a patient appointment request (Doctor role required)",
)
async def reject_appointment_request(
    appointment_id: str,
    payload: UpdateAppointmentStatusRequest = None,
    token: str = Depends(oauth2_scheme),
) -> dict:
    """Doctor rejects a patient's pending appointment request with optional reason."""
    try:
        user_details = decodeJWT(token)
        if not user_details:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        reason = payload.reason if payload else "Doctor declined appointment request."
        return await PrescriptionController().update_appointment_status(
            appointment_id=appointment_id,
            new_status=AppointmentStatus.REJECTED,
            authenticated_user_details=user_details,
            reason=reason,
        )
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to reject appointment %s: %s", appointment_id, str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.post(
    "/v1/doctor/prescriptions",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a prescription for an accepted patient (Doctor role required)",
)
async def create_prescription_endpoint(
    payload: CreatePrescriptionRequest,
    token: str = Depends(oauth2_scheme),
) -> PrescriptionResponse:
    """
    Doctor creates a medical prescription.

    Generates a PDF format document, uploads to Cloudinary, and registers the prescription in RAG pipeline.
    """
    try:
        user_details = decodeJWT(token)
        if not user_details:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return await PrescriptionController().create_prescription(
            payload=payload,
            authenticated_user_details=user_details,
        )
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to create prescription: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/patient/prescriptions",
    response_model=List[PrescriptionResponse],
    status_code=status.HTTP_200_OK,
    summary="List all prescriptions for the authenticated patient",
)
async def list_my_prescriptions_endpoint(
    token: str = Depends(oauth2_scheme),
) -> List[PrescriptionResponse]:
    """Retrieve all prescriptions issued for the authenticated patient."""
    try:
        user_details = decodeJWT(token)
        if not user_details:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return await PrescriptionController().list_patient_prescriptions(
            authenticated_user_details=user_details,
        )
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to list patient prescriptions: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/patient/prescriptions/{prescription_id}",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get detailed prescription record",
)
async def get_prescription_endpoint(
    prescription_id: str,
    token: str = Depends(oauth2_scheme),
) -> PrescriptionResponse:
    """Retrieve details for a single prescription."""
    try:
        user_details = decodeJWT(token)
        if not user_details:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return await PrescriptionController().get_prescription_details(
            prescription_id=prescription_id,
            authenticated_user_details=user_details,
        )
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to get prescription %s: %s", prescription_id, str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/patient/prescriptions/{prescription_id}/pdf",
    summary="View / Download prescription PDF file",
)
async def view_prescription_pdf(
    prescription_id: str,
    token: Optional[str] = Query(None),
):
    """
    Streams or redirects to the PDF format prescription file.
    Redirects to Cloudinary URL if available, or streams local PDF file fallback.
    """
    try:
        local_path = os.path.join(LOCAL_PRESCRIPTION_DIR, f"{prescription_id}.pdf")
        if os.path.exists(local_path):
            return FileResponse(
                path=local_path,
                media_type="application/pdf",
                headers={"Content-Disposition": f"inline; filename=Prescription-{prescription_id}.pdf"},
            )

        if token:
            user_details = decodeJWT(token)
            if user_details:
                p = await PrescriptionController().get_prescription_details(
                    prescription_id=prescription_id,
                    authenticated_user_details=user_details,
                )
                if p.pdf_url.startswith("http://") or p.pdf_url.startswith("https://"):
                    return RedirectResponse(url=p.pdf_url)

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription PDF file not found on disk.",
        )
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to fetch prescription PDF %s: %s", prescription_id, str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.get(
    "/v1/patient/prescriptions/{prescription_id}/pdf-file",
    summary="Local PDF fallback file stream endpoint",
    include_in_schema=False,
)
async def get_local_pdf_file(prescription_id: str):
    """Local fallback endpoint serving PDF bytes directly."""
    local_path = os.path.join(LOCAL_PRESCRIPTION_DIR, f"{prescription_id}.pdf")
    if not os.path.exists(local_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Local PDF file not found.",
        )
    return FileResponse(
        path=local_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=Prescription-{prescription_id}.pdf"},
    )
