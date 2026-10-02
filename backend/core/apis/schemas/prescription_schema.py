"""
─────────────────────────────────────────────────────────────────────────────
File        : core/apis/schemas/prescription_schema.py
Purpose     : Pydantic request and response schemas for prescription operations.

Used By:
    - core/apis/routes/prescription_routes.py
    - core/controllers/prescription_controller.py
─────────────────────────────────────────────────────────────────────────────
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from core.constants import AppointmentStatus


class MedicationItemSchema(BaseModel):
    """Schema for an individual medication entry in a prescription."""

    medicine_name: str = Field(..., description="Name of the prescribed medicine", examples=["Paracetamol"])
    dosage: str = Field(..., description="Dosage amount", examples=["500 mg"])
    frequency: str = Field(..., description="Daily frequency schedule", examples=["1-0-1 after meals"])
    duration: str = Field(..., description="Duration of medication course", examples=["5 days"])
    instructions: Optional[str] = Field(default=None, description="Special instructions", examples=["Take with warm water"])


class CreatePrescriptionRequest(BaseModel):
    """Request payload for doctor to create a prescription for an accepted appointment."""

    appointment_id: str = Field(..., min_length=24, max_length=24, description="Target appointment ObjectId")
    diagnosis: str = Field(..., min_length=3, description="Clinical diagnosis or assessment")
    medications: List[MedicationItemSchema] = Field(..., min_length=1, description="List of prescribed medicines")
    notes: Optional[str] = Field(default=None, description="General doctor advice, dietary or lifestyle notes")
    follow_up_date: Optional[str] = Field(default=None, description="Recommended follow-up date (YYYY-MM-DD)")


class PrescriptionResponse(BaseModel):
    """Response payload representing a full prescription record."""

    prescription_id: str = Field(..., description="Unique ID of prescription document")
    hospital_id: str = Field(..., description="Tenant hospital ID")
    doctor_id: str = Field(..., description="Doctor ID")
    doctor_name: str = Field(..., description="Doctor full name")
    patient_id: str = Field(..., description="Patient ID")
    patient_name: str = Field(..., description="Patient full name")
    appointment_id: str = Field(..., description="Associated appointment ID")
    date: str = Field(..., description="Prescription issuance date (YYYY-MM-DD)")
    diagnosis: str = Field(..., description="Clinical diagnosis")
    medications: List[MedicationItemSchema] = Field(..., description="List of prescribed medicines")
    notes: Optional[str] = Field(default=None, description="Doctor notes/advice")
    follow_up_date: Optional[str] = Field(default=None, description="Follow-up date")
    pdf_url: str = Field(..., description="URL to view/download PDF prescription")
    created_at: str = Field(..., description="Creation timestamp ISO string")


class UpdateAppointmentStatusRequest(BaseModel):
    """Request payload for doctor to accept or reject an appointment."""

    status: AppointmentStatus = Field(..., description="New appointment status: 'accepted' or 'rejected'")
    reason: Optional[str] = Field(default=None, description="Optional rejection reason")
