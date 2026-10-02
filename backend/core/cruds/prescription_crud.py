"""
─────────────────────────────────────────────────────────────────────────────
File        : core/cruds/prescription_crud.py
Purpose     : MongoDB database query operations for PrescriptionModel documents.

Used By:
    - core/controllers/prescription_controller.py
─────────────────────────────────────────────────────────────────────────────
"""

from typing import List, Optional
from bson import ObjectId
from odmantic import AIOEngine

from common.logger import get_logger
from core.models.prescription_model import PrescriptionModel

logger = get_logger(__name__)


async def create_prescription(
    engine: AIOEngine,
    prescription: PrescriptionModel,
) -> PrescriptionModel:
    """
    Save a new prescription document in MongoDB.

    Args:
        engine: ODMantic MongoDB engine.
        prescription: PrescriptionModel instance.

    Returns:
        PrescriptionModel: Saved document.
    """
    saved = await engine.save(prescription)
    logger.info("Saved prescription ID=%s for appointment=%s", str(saved.id), saved.appointment_id)
    return saved


async def find_prescription_by_id(
    engine: AIOEngine,
    prescription_id: str,
) -> Optional[PrescriptionModel]:
    """
    Find prescription document by ObjectId string.
    """
    try:
        obj_id = ObjectId(prescription_id)
        return await engine.find_one(PrescriptionModel, PrescriptionModel.id == obj_id)
    except Exception:
        return None


async def find_prescription_by_appointment(
    engine: AIOEngine,
    appointment_id: str,
) -> Optional[PrescriptionModel]:
    """
    Find prescription by associated appointment ID string.
    """
    return await engine.find_one(PrescriptionModel, PrescriptionModel.appointment_id == appointment_id)


async def find_prescriptions_by_patient(
    engine: AIOEngine,
    patient_id: str,
) -> List[PrescriptionModel]:
    """
    Retrieve all prescriptions issued for a specific patient, ordered newest first.
    """
    return await engine.find(
        PrescriptionModel,
        PrescriptionModel.patient_id == patient_id,
        sort=PrescriptionModel.created_at.desc(),
    )


async def find_prescriptions_by_doctor(
    engine: AIOEngine,
    hospital_id: str,
    doctor_id: str,
) -> List[PrescriptionModel]:
    """
    Retrieve all prescriptions created by a doctor at a hospital, ordered newest first.
    """
    return await engine.find(
        PrescriptionModel,
        (PrescriptionModel.hospital_id == hospital_id) & (PrescriptionModel.doctor_id == doctor_id),
        sort=PrescriptionModel.created_at.desc(),
    )
