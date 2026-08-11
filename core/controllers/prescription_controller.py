"""
─────────────────────────────────────────────────────────────────────────────
File        : core/controllers/prescription_controller.py
Purpose     : Controller orchestrator for prescription generation and RAG ingestion.

Used By:
    - core/apis/routes/prescription_routes.py
─────────────────────────────────────────────────────────────────────────────
"""

from typing import List, Optional
from bson import ObjectId
from fastapi import HTTPException, status

from common.logger import get_logger
from core.apis.schemas.prescription_schema import (
    CreatePrescriptionRequest,
    MedicationItemSchema,
    PrescriptionResponse,
)
from core.constants import AppointmentStatus, DOCTOR_INFO, UserRole
from core.cruds.appointment_crud import find_appointment_by_id
from core.cruds.doctor_profile_crud import find_profile_by_user_id
from core.cruds.hospital_crud import find_hospital_by_id
from core.cruds.prescription_crud import (
    create_prescription,
    find_prescription_by_appointment,
    find_prescription_by_id,
    find_prescriptions_by_patient,
)
from core.database.database import get_engine
from core.models.appointment_model import AppointmentModel
from core.models.prescription_model import PrescriptionModel
from core.services.cloudinary_service import upload_prescription_pdf
from core.services.pdf_service import generate_prescription_pdf

logger = get_logger(__name__)


class PrescriptionController:
    """Business logic controller for patient prescriptions and appointment status updates."""

    async def update_appointment_status(
        self,
        appointment_id: str,
        new_status: AppointmentStatus,
        authenticated_user_details: dict,
        reason: Optional[str] = None,
    ) -> dict:
        """
        Doctor accepts or rejects a patient appointment request.
        """
        role = authenticated_user_details.get("role")
        if role != UserRole.DOCTOR.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Doctor role required to manage appointment requests.",
            )

        engine = get_engine()
        doctor_user_id = authenticated_user_details.get("user_id") or ""
        hospital_id = authenticated_user_details.get("hospital_id") or ""
        appointment = await find_appointment_by_id(engine, appointment_id, hospital_id=hospital_id if hospital_id else None)

        if not appointment or appointment.is_cancelled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Appointment '{appointment_id}' not found or active.",
            )

        # Scoping check: verify appointment belongs to doctor's hospital
        if hospital_id and appointment.hospital_id != hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Appointment belongs to another clinic tenant.",
            )

        # Doctor ownership check: verify appointment is assigned to this doctor
        valid_doctor_ids = [doctor_user_id]
        if doctor_user_id:
            profile = await find_profile_by_user_id(engine, doctor_user_id)
            if profile:
                valid_doctor_ids.append(str(profile.id))

        if appointment.doctor_id and appointment.doctor_id not in valid_doctor_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Appointment is assigned to another doctor.",
            )

        appointment.status = new_status
        if new_status == AppointmentStatus.REJECTED and reason:
            appointment.cancellation_reason = reason

        await engine.save(appointment)
        logger.info("Doctor updated appointment %s status to %s", appointment_id, new_status.value)
        return {
            "appointment_id": appointment_id,
            "status": new_status.value,
            "message": f"Appointment request has been {new_status.value}.",
        }

    async def create_prescription(
        self,
        payload: CreatePrescriptionRequest,
        authenticated_user_details: dict,
    ) -> PrescriptionResponse:
        """
        Doctor creates a prescription for an accepted patient appointment.
        """
        role = authenticated_user_details.get("role")
        if role != UserRole.DOCTOR.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Only doctors can issue prescriptions.",
            )

        engine = get_engine()
        doctor_user_id = authenticated_user_details.get("user_id") or ""
        doctor_name = authenticated_user_details.get("name") or DOCTOR_INFO["doctor_name"]
        hospital_id = authenticated_user_details.get("hospital_id") or ""

        # 1. Fetch & validate appointment
        appointment = await find_appointment_by_id(engine, payload.appointment_id, hospital_id=hospital_id if hospital_id else None)
        if not appointment or appointment.is_cancelled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Appointment '{payload.appointment_id}' not found.",
            )

        # Doctor ownership check: verify appointment is assigned to this doctor
        valid_doctor_ids = [doctor_user_id]
        if doctor_user_id:
            profile = await find_profile_by_user_id(engine, doctor_user_id)
            if profile:
                valid_doctor_ids.append(str(profile.id))

        if appointment.doctor_id and appointment.doctor_id not in valid_doctor_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Appointment is assigned to another doctor.",
            )

        # If status was pending, auto accept upon prescription creation
        if appointment.status in (AppointmentStatus.PENDING, AppointmentStatus.ACCEPTED):
            appointment.status = AppointmentStatus.COMPLETED
        elif appointment.status == AppointmentStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot issue prescription for a rejected appointment.",
            )

        # Check if prescription already created for this appointment
        existing_p = await find_prescription_by_appointment(engine, payload.appointment_id)
        if existing_p:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Prescription already exists for appointment '{payload.appointment_id}'.",
            )

        # 2. Fetch hospital info for PDF header
        hospital_name = DOCTOR_INFO["clinic_name"]
        specialization = DOCTOR_INFO["specialization"]
        clinic_address = DOCTOR_INFO["address"]
        clinic_phone = DOCTOR_INFO["phone"]

        if hospital_id:
            hospital = await find_hospital_by_id(engine, hospital_id)
            if hospital:
                hospital_name = hospital.name
                clinic_address = hospital.address
                clinic_phone = hospital.contact_number

        medications_dict_list = [m.model_dump() for m in payload.medications]

        # 3. Create initial prescription MongoDB model
        prescription_doc = PrescriptionModel(
            hospital_id=appointment.hospital_id,
            doctor_id=doctor_user_id,
            doctor_name=doctor_name,
            patient_id=appointment.patient_id,
            patient_name=appointment.patient_name,
            appointment_id=payload.appointment_id,
            date=appointment.date,
            diagnosis=payload.diagnosis,
            medications=medications_dict_list,
            notes=payload.notes,
            follow_up_date=payload.follow_up_date,
            pdf_url="",
        )

        saved_prescription = await create_prescription(engine, prescription_doc)
        prescription_id = str(saved_prescription.id)

        # 4. Dynamic PDF Generation
        symptoms_list = [s.value for s in appointment.symptoms] if appointment.symptoms else []
        pdf_bytes = generate_prescription_pdf(
            prescription_id=prescription_id,
            hospital_name=hospital_name,
            doctor_name=doctor_name,
            specialization=specialization,
            clinic_address=clinic_address,
            clinic_phone=clinic_phone,
            patient_name=appointment.patient_name,
            date_str=appointment.date,
            appointment_id=payload.appointment_id,
            diagnosis=payload.diagnosis,
            medications=medications_dict_list,
            notes=payload.notes,
            follow_up_date=payload.follow_up_date,
            temperature=appointment.temperature,
            symptoms=symptoms_list,
        )

        # 5. Cloudinary / Local Storage Upload
        pdf_url, public_id = await upload_prescription_pdf(pdf_bytes, prescription_id)
        saved_prescription.pdf_url = pdf_url
        saved_prescription.cloudinary_public_id = public_id
        await engine.save(saved_prescription)
        await engine.save(appointment)

        # 6. Ingest into RAG Vector Store
        try:
            from chatbot.rag_service import ingest_prescription_doc
            ingest_prescription_doc(saved_prescription)
        except Exception as rag_err:
            logger.error("Failed auto-ingesting prescription %s into RAG vector store: %s", prescription_id, str(rag_err))

        return PrescriptionResponse(
            prescription_id=prescription_id,
            hospital_id=saved_prescription.hospital_id,
            doctor_id=saved_prescription.doctor_id,
            doctor_name=saved_prescription.doctor_name,
            patient_id=saved_prescription.patient_id,
            patient_name=saved_prescription.patient_name,
            appointment_id=saved_prescription.appointment_id,
            date=saved_prescription.date,
            diagnosis=saved_prescription.diagnosis,
            medications=[MedicationItemSchema(**m) for m in saved_prescription.medications],
            notes=saved_prescription.notes,
            follow_up_date=saved_prescription.follow_up_date,
            pdf_url=saved_prescription.pdf_url,
            created_at=saved_prescription.created_at.isoformat() if saved_prescription.created_at else "",
        )

    async def list_patient_prescriptions(
        self,
        authenticated_user_details: dict,
    ) -> List[PrescriptionResponse]:
        """
        List all prescriptions for the currently authenticated patient.
        """
        patient_id = authenticated_user_details.get("user_id") or ""
        engine = get_engine()
        prescriptions = await find_prescriptions_by_patient(engine, patient_id)

        return [
            PrescriptionResponse(
                prescription_id=str(p.id),
                hospital_id=p.hospital_id,
                doctor_id=p.doctor_id,
                doctor_name=p.doctor_name,
                patient_id=p.patient_id,
                patient_name=p.patient_name,
                appointment_id=p.appointment_id,
                date=p.date,
                diagnosis=p.diagnosis,
                medications=[MedicationItemSchema(**m) for m in p.medications],
                notes=p.notes,
                follow_up_date=p.follow_up_date,
                pdf_url=p.pdf_url,
                created_at=p.created_at.isoformat() if p.created_at else "",
            )
            for p in prescriptions
        ]

    async def get_prescription_details(
        self,
        prescription_id: str,
        authenticated_user_details: dict,
    ) -> PrescriptionResponse:
        """
        Retrieve single prescription details. Authorized for patient owner or doctor.
        """
        engine = get_engine()
        p = await find_prescription_by_id(engine, prescription_id)
        if not p:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prescription '{prescription_id}' not found.",
            )

        user_id = authenticated_user_details.get("user_id") or ""
        role = authenticated_user_details.get("role") or ""

        # Authorization: patient must own it, or doctor/hospital owner must belong to hospital
        if role == UserRole.PATIENT.value and p.patient_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view your own prescriptions.",
            )

        return PrescriptionResponse(
            prescription_id=str(p.id),
            hospital_id=p.hospital_id,
            doctor_id=p.doctor_id,
            doctor_name=p.doctor_name,
            patient_id=p.patient_id,
            patient_name=p.patient_name,
            appointment_id=p.appointment_id,
            date=p.date,
            diagnosis=p.diagnosis,
            medications=[MedicationItemSchema(**m) for m in p.medications],
            notes=p.notes,
            follow_up_date=p.follow_up_date,
            pdf_url=p.pdf_url,
            created_at=p.created_at.isoformat() if p.created_at else "",
        )
