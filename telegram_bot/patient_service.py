"""Patient-domain facade used by Telegram without duplicating web authentication."""

import secrets
from datetime import date, timedelta
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException, status
from odmantic import AIOEngine
from pymongo.errors import DuplicateKeyError

from common.auth import hash_password
from core.apis.schemas.appointment_schema import BookAppointmentRequest
from core.apis.schemas.discovery_schema import (
    DoctorDiscoveryResponse,
    DoctorFreeSlotsResponse,
)
from core.constants import MAX_BOOKING_DAYS, UserRole, calculate_free_slots
from core.controllers.appointment_controller import AppointmentController
from core.controllers.prescription_controller import PrescriptionController
from core.cruds.appointment_crud import find_booked_slots_by_date
from core.cruds.doctor_profile_crud import find_profile_by_id, find_profiles_by_hospital
from core.cruds.hospital_crud import find_all_hospitals, find_hospital_by_id
from core.cruds.user_crud import create_user, find_user_by_email
from core.models.user_model import UserModel
from telegram_bot.schemas import TelegramHospital


class TelegramPatientService:
    """Narrow gateway onto existing patient-side Medihub operations."""

    def __init__(self, engine: AIOEngine):
        self.engine = engine

    async def list_hospitals(self, search: str = "") -> List[TelegramHospital]:
        """Return active, approved hospitals and patient-visible services."""
        query = search.strip().casefold()
        hospitals = await find_all_hospitals(self.engine)
        return [
            TelegramHospital(
                hospital_id=str(hospital.id),
                name=hospital.name,
                city=hospital.city,
                address=hospital.address,
                contact_number=hospital.contact_number,
                facilities=hospital.facilities,
                services=hospital.services,
                is_active=hospital.is_active,
            )
            for hospital in hospitals
            if hospital.is_active
            and hospital.is_approved
            and (
                not query
                or query in hospital.name.casefold()
                or query in hospital.city.casefold()
                or query in hospital.address.casefold()
            )
        ]

    async def get_hospital(self, hospital_id: str) -> TelegramHospital:
        """Return one active, approved hospital or a patient-safe 404."""
        hospital = await find_hospital_by_id(self.engine, hospital_id)
        if not hospital or not hospital.is_active or not hospital.is_approved:
            raise HTTPException(status_code=404, detail="Hospital is not available.")
        return TelegramHospital(
            hospital_id=str(hospital.id),
            name=hospital.name,
            city=hospital.city,
            address=hospital.address,
            contact_number=hospital.contact_number,
            facilities=hospital.facilities,
            services=hospital.services,
            is_active=hospital.is_active,
        )

    async def list_doctors(
        self, hospital_id: Optional[str] = None, specialization: str = ""
    ) -> List[DoctorDiscoveryResponse]:
        """List active doctors, optionally filtered by hospital and specialization."""
        hospital_ids: list[str]
        if hospital_id:
            await self.get_hospital(hospital_id)
            hospital_ids = [hospital_id]
        else:
            hospital_ids = [item.hospital_id for item in await self.list_hospitals()]

        profiles = []
        for current_hospital_id in hospital_ids:
            profiles.extend(
                await find_profiles_by_hospital(self.engine, current_hospital_id)
            )
        profiles = [profile for profile in profiles if profile.is_active]
        query = specialization.strip().casefold()
        if query:
            profiles = [
                profile
                for profile in profiles
                if query in profile.specialization.casefold()
            ]

        user_ids = []
        for profile in profiles:
            try:
                user_ids.append(ObjectId(profile.user_id))
            except Exception:
                continue
        users = (
            await self.engine.find(UserModel, UserModel.id.in_(user_ids))
            if user_ids
            else []
        )
        users_by_id = {str(user.id): user for user in users}
        return [
            DoctorDiscoveryResponse(
                profile_id=str(profile.id),
                user_id=profile.user_id,
                name=users_by_id.get(profile.user_id).name
                if users_by_id.get(profile.user_id)
                else "Doctor",
                email=users_by_id.get(profile.user_id).email
                if users_by_id.get(profile.user_id)
                else "",
                specialization=profile.specialization,
                consultation_fee=profile.consultation_fee,
                clinic_hours=profile.clinic_hours,
                languages_spoken=profile.languages_spoken,
                unavailable_dates=profile.unavailable_dates or [],
                is_active=profile.is_active,
            )
            for profile in profiles
        ]

    async def available_slots(
        self, hospital_id: str, doctor_id: str, requested_date: str
    ) -> DoctorFreeSlotsResponse:
        """Apply the same hospital, doctor, date, and booking-window checks as the API."""
        try:
            parsed_date = date.fromisoformat(requested_date)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Use date format YYYY-MM-DD.") from error
        today = date.today()
        if parsed_date < today or parsed_date > today + timedelta(days=MAX_BOOKING_DAYS):
            raise HTTPException(
                status_code=400,
                detail=f"Choose a date from today through {MAX_BOOKING_DAYS} days ahead.",
            )
        await self.get_hospital(hospital_id)
        profile = await find_profile_by_id(self.engine, hospital_id, doctor_id)
        if not profile or not profile.is_active:
            raise HTTPException(status_code=404, detail="Doctor is not available.")
        unavailable = requested_date in (profile.unavailable_dates or [])
        booked = (
            []
            if unavailable
            else await find_booked_slots_by_date(
                self.engine, hospital_id, doctor_id, requested_date
            )
        )
        slots = [] if unavailable else calculate_free_slots(booked)
        return DoctorFreeSlotsResponse(
            hospital_id=hospital_id,
            doctor_id=doctor_id,
            date=requested_date,
            available_slots=slots,
            total_available=len(slots),
            is_unavailable=unavailable,
        )

    async def register_patient(
        self,
        name: str,
        email: str,
        phone_number: str,
        telegram_user_id: str,
    ) -> UserModel:
        """Create a Telegram-native patient without collecting a reusable password."""
        clean_email = email.strip().lower()
        if await find_user_by_email(self.engine, clean_email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already registered. Use /link with a one-time code.",
            )
        user = UserModel(
            name=name.strip(),
            email=clean_email,
            phone_number=phone_number.strip(),
            telegram_user_id=telegram_user_id,
            registration_source="telegram",
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            role=UserRole.PATIENT,
        )
        try:
            return await create_user(self.engine, user)
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=409,
                detail="That email or Telegram account is already registered.",
            ) from error

    @staticmethod
    def patient_context(patient: UserModel) -> dict:
        """Build the identity shape expected by existing patient controllers."""
        return {
            "user_id": str(patient.id),
            "name": patient.name,
            "email": patient.email,
            "role": UserRole.PATIENT.value,
            "hospital_id": None,
        }

    async def book(self, patient: UserModel, request: BookAppointmentRequest):
        """Book through the existing four-gate appointment controller."""
        return await AppointmentController().book_appointment(
            booking_request=request,
            authenticated_user_details=self.patient_context(patient),
        )

    async def appointments(self, patient: UserModel):
        """List only the linked patient's appointments."""
        return await AppointmentController().list_my_appointments(
            authenticated_user_details=self.patient_context(patient)
        )

    async def prescriptions(self, patient: UserModel):
        """List only the linked patient's prescriptions."""
        return await PrescriptionController().list_patient_prescriptions(
            authenticated_user_details=self.patient_context(patient)
        )
