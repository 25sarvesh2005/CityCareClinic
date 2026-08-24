"""Hermes-inspired Telegram message gateway and patient workflow state machine."""

import asyncio
import hashlib
import json
import re
import weakref
from datetime import datetime, timezone
from typing import Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException
from odmantic import AIOEngine
from pydantic import EmailStr, TypeAdapter, ValidationError
from pymongo.errors import DuplicateKeyError

from core.apis.schemas.appointment_schema import BookAppointmentRequest
from core.constants import Symptom, UserRole
from core.cruds.user_crud import (
    find_user_by_telegram_id,
    link_user_to_telegram,
)
from core.models.doctor_profile_model import DoctorProfileModel
from core.models.user_model import UserModel
from telegram_bot.cruds import (
    add_message,
    clear_messages,
    find_update,
    get_or_create_session,
    mark_update_delivered,
    recent_messages,
    save_session,
    save_update,
)
from telegram_bot.medical_assistant import answer_medical_message
from telegram_bot.models import TelegramSessionModel
from telegram_bot.patient_service import TelegramPatientService
from telegram_bot.schemas import TelegramDispatch, TelegramReply


EMAIL_ADAPTER = TypeAdapter(EmailStr)
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 -]{6,18}[0-9]$")


def hash_link_code(code: str) -> str:
    """Hash a one-time account link code before database lookup or storage."""
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def inline_keyboard(rows: List[List[tuple[str, str]]]) -> dict:
    """Build Telegram Bot API inline-keyboard JSON."""
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": data} for label, data in row]
            for row in rows
        ]
    }


class TelegramGateway:
    """Normalize updates, isolate sessions, run workflows, and persist replies."""

    _locks: "weakref.WeakValueDictionary[str, asyncio.Lock]" = weakref.WeakValueDictionary()

    def __init__(self, engine: AIOEngine):
        self.engine = engine
        self.service = TelegramPatientService(engine)

    async def handle_update(self, update: dict) -> TelegramDispatch:
        """Process one update exactly once and durably retain outbound replies."""
        update_id = int(update.get("update_id", -1))
        if update_id < 0:
            raise HTTPException(status_code=400, detail="Telegram update_id is required.")
        existing = await find_update(self.engine, update_id)
        callback_query_id = (update.get("callback_query") or {}).get("id")
        if existing:
            replies = [] if existing.delivered else [
                TelegramReply.model_validate(item)
                for item in json.loads(existing.replies_json)
            ]
            return TelegramDispatch(
                update_id=update_id,
                replies=replies,
                replayed=True,
                callback_query_id=callback_query_id,
            )

        normalized = self._normalize(update)
        if not normalized:
            dispatch = TelegramDispatch(update_id=update_id)
            await save_update(self.engine, update_id, "unknown", "[]")
            return dispatch

        user_id, chat_id, chat_type, username, text = normalized
        if chat_type != "private":
            replies = [
                TelegramReply(
                    chat_id=chat_id,
                    text="For privacy, the Medihub patient assistant works only in a private chat. Please message the bot directly.",
                )
            ]
            await save_update(
                self.engine,
                update_id,
                chat_id,
                json.dumps([reply.model_dump(exclude_none=True) for reply in replies]),
            )
            return TelegramDispatch(
                update_id=update_id,
                replies=replies,
                callback_query_id=callback_query_id,
            )
        lock = self._locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            existing = await find_update(self.engine, update_id)
            if existing:
                replies = [] if existing.delivered else [
                    TelegramReply.model_validate(item)
                    for item in json.loads(existing.replies_json)
                ]
                return TelegramDispatch(
                    update_id=update_id,
                    replies=replies,
                    replayed=True,
                    callback_query_id=callback_query_id,
                )

            session = await get_or_create_session(
                self.engine, user_id, chat_id, username
            )
            linked = await find_user_by_telegram_id(self.engine, user_id)
            if linked and linked.role == UserRole.PATIENT:
                session.patient_id = str(linked.id)
                await save_session(self.engine, session)

            try:
                replies = await self._dispatch(session, text, chat_id)
            except HTTPException as error:
                replies = [TelegramReply(chat_id=chat_id, text=str(error.detail))]
            except (ValidationError, ValueError) as error:
                replies = [TelegramReply(chat_id=chat_id, text=str(error))]

            replies_json = json.dumps(
                [reply.model_dump(exclude_none=True) for reply in replies]
            )
            try:
                await save_update(self.engine, update_id, chat_id, replies_json)
            except DuplicateKeyError:
                recorded = await find_update(self.engine, update_id)
                if recorded:
                    replies = [] if recorded.delivered else [
                        TelegramReply.model_validate(item)
                        for item in json.loads(recorded.replies_json)
                    ]
            return TelegramDispatch(
                update_id=update_id,
                replies=replies,
                callback_query_id=callback_query_id,
            )

    async def mark_delivered(self, update_id: int) -> None:
        """Mark all replies for one update as accepted by Telegram."""
        await mark_update_delivered(self.engine, update_id)

    @staticmethod
    def _normalize(
        update: dict,
    ) -> Optional[tuple[str, str, str, Optional[str], str]]:
        callback = update.get("callback_query") or {}
        message = callback.get("message") or update.get("message") or {}
        sender = callback.get("from") or message.get("from") or {}
        chat = message.get("chat") or {}
        if not sender.get("id") or not chat.get("id"):
            return None
        text = callback.get("data")
        if text is None:
            text = message.get("text")
        if text is None and message.get("contact"):
            text = message["contact"].get("phone_number")
        if text is None:
            text = ""
        return (
            str(sender["id"]),
            str(chat["id"]),
            str(chat.get("type", "")),
            sender.get("username"),
            str(text).strip(),
        )

    async def _dispatch(
        self, session: TelegramSessionModel, text: str, chat_id: str
    ) -> List[TelegramReply]:
        command, _, argument = text.partition(" ")
        command = command.casefold()

        if command in {"/start", "/help"}:
            return [self._welcome(session, chat_id)]
        if command in {"/reset", "/cancel"}:
            self._clear_workflow(session)
            await clear_messages(self.engine, str(session.id))
            await save_session(self.engine, session)
            return [TelegramReply(chat_id=chat_id, text="Conversation reset. Your account link is still active."), self._welcome(session, chat_id)]
        if command == "/register":
            if await self._patient(session):
                return [TelegramReply(chat_id=chat_id, text="Your Telegram account is already registered and linked.")]
            self._clear_workflow(session)
            session.state = "register_name"
            await save_session(self.engine, session)
            return [TelegramReply(chat_id=chat_id, text="What is your full name?")]
        if command == "/link":
            if await self._patient(session):
                return [TelegramReply(chat_id=chat_id, text="This Telegram account is already linked.")]
            if argument.strip():
                return await self._link(session, argument.strip(), chat_id)
            session.state = "link_code"
            await save_session(self.engine, session)
            return [TelegramReply(chat_id=chat_id, text="Send the one-time link code generated from your authenticated Medihub account.")]
        if command == "/hospitals":
            return await self._hospitals(chat_id)
        if command == "/doctors":
            return await self._doctors(chat_id, session.selected_hospital_id)
        if command in {"/speciality", "/specialization"}:
            if argument.strip():
                return await self._specialization(chat_id, argument.strip())
            session.state = "specialization"
            await save_session(self.engine, session)
            return [TelegramReply(chat_id=chat_id, text="Which specialization are you looking for? For example: cardiologist or general physician.")]
        if command == "/facilities":
            if session.selected_hospital_id:
                return [await self._facility_reply(chat_id, session.selected_hospital_id)]
            return await self._hospital_choices(chat_id, "Choose a hospital to view facilities:", "facilities")
        if command == "/book":
            if not await self._patient(session):
                return [self._registration_required(chat_id)]
            if session.selected_hospital_id and session.selected_doctor_id:
                return await self._begin_booking(session, chat_id)
            return await self._hospital_choices(chat_id, "Choose a hospital, then select a doctor:", "doctors")
        if command == "/appointments":
            return await self._appointments(session, chat_id)
        if command == "/prescriptions":
            return await self._prescriptions(session, chat_id)

        if text == "menu:hospitals":
            return await self._hospitals(chat_id)
        if text == "menu:doctors":
            return await self._doctors(chat_id, session.selected_hospital_id)

        if text.startswith("hospital:"):
            hospital_id = text.split(":", 1)[1]
            session.selected_hospital_id = hospital_id
            session.selected_doctor_id = None
            await save_session(self.engine, session)
            hospital = await self.service.get_hospital(hospital_id)
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text=f"🏥 {hospital.name}\n{hospital.address}, {hospital.city}\nContact: {hospital.contact_number}",
                    reply_markup=inline_keyboard([
                        [("👨‍⚕️ Doctors", f"doctors:{hospital_id}"), ("🏥 Facilities", f"facilities:{hospital_id}")]
                    ]),
                )
            ]
        if text.startswith("doctors:"):
            return await self._doctors(chat_id, text.split(":", 1)[1])
        if text.startswith("facilities:"):
            return [await self._facility_reply(chat_id, text.split(":", 1)[1])]
        if text.startswith("doctor:"):
            _, hospital_id, doctor_id = text.split(":", 2)
            return [await self._doctor_reply(session, chat_id, hospital_id, doctor_id)]
        if text.startswith("book:"):
            _, hospital_id, doctor_id = text.split(":", 2)
            session.selected_hospital_id = hospital_id
            session.selected_doctor_id = doctor_id
            return await self._begin_booking(session, chat_id)
        if text.startswith("slot:") and session.state == "book_slot":
            session.booking_slot = text.split(":", 1)[1]
            session.state = "book_reason"
            await save_session(self.engine, session)
            return [TelegramReply(chat_id=chat_id, text="Briefly describe the reason for the visit (at least 10 characters).")]
        if text == "confirm_booking" and session.state == "book_confirm":
            return await self._confirm_booking(session, chat_id)
        if text == "cancel_booking":
            self._clear_workflow(session)
            await save_session(self.engine, session)
            return [TelegramReply(chat_id=chat_id, text="Booking cancelled. No appointment was created.")]

        state_handler = getattr(self, f"_state_{session.state}", None)
        if state_handler:
            return await state_handler(session, text, chat_id)

        history = [
            {"role": item.role, "content": item.content}
            for item in await recent_messages(self.engine, str(session.id))
        ]
        await add_message(self.engine, str(session.id), "user", text)
        answer = await answer_medical_message(text, history)
        await add_message(self.engine, str(session.id), "assistant", answer)
        return [TelegramReply(chat_id=chat_id, text=answer)]

    def _welcome(self, session: TelegramSessionModel, chat_id: str) -> TelegramReply:
        linked = bool(session.patient_id)
        identity = "✅ Patient account linked" if linked else "ℹ️ Not registered yet — use /register or /link"
        return TelegramReply(
            chat_id=chat_id,
            text=(
                "Welcome to the Medihub Patient Assistant.\n"
                f"{identity}\n\n"
                "Chat about a health concern, or use:\n"
                "/hospitals — hospital list\n/doctors — available doctors\n"
                "/speciality — find a specialist\n/book — book an appointment\n"
                "/facilities — hospital services\n/appointments — your appointments\n"
                "/prescriptions — your prescriptions\n/reset — reset this conversation"
            ),
            reply_markup=inline_keyboard([
                [("🏥 Hospitals", "menu:hospitals"), ("👨‍⚕️ Doctors", "menu:doctors")]
            ]),
        )

    async def _patient(self, session: TelegramSessionModel) -> Optional[UserModel]:
        if not session.patient_id:
            return None
        try:
            patient = await self.engine.find_one(
                UserModel, UserModel.id == ObjectId(session.patient_id)
            )
        except Exception:
            patient = None
        if not patient or patient.role != UserRole.PATIENT or patient.telegram_user_id != session.telegram_user_id:
            session.patient_id = None
            await save_session(self.engine, session)
            return None
        return patient

    @staticmethod
    def _registration_required(chat_id: str) -> TelegramReply:
        return TelegramReply(
            chat_id=chat_id,
            text="Registration is required for private patient operations. Use /register for a new account or /link CODE for an existing account.",
        )

    async def _hospital_choices(self, chat_id: str, heading: str, action: str) -> List[TelegramReply]:
        hospitals = await self.service.list_hospitals()
        if not hospitals:
            return [TelegramReply(chat_id=chat_id, text="No active hospitals are available right now.")]
        rows = [[(f"{item.name} — {item.city}", f"{action}:{item.hospital_id}")] for item in hospitals[:20]]
        return [TelegramReply(chat_id=chat_id, text=heading, reply_markup=inline_keyboard(rows))]

    async def _hospitals(self, chat_id: str) -> List[TelegramReply]:
        return await self._hospital_choices(chat_id, "Available hospitals:", "hospital")

    async def _doctors(self, chat_id: str, hospital_id: Optional[str]) -> List[TelegramReply]:
        if not hospital_id:
            return await self._hospital_choices(chat_id, "Choose a hospital to view doctors:", "doctors")
        doctors = await self.service.list_doctors(hospital_id=hospital_id)
        if not doctors:
            return [TelegramReply(chat_id=chat_id, text="No active doctors are listed at this hospital.")]
        rows = [[(f"{doctor.name} — {doctor.specialization}", f"doctor:{hospital_id}:{doctor.profile_id}")] for doctor in doctors[:20]]
        return [TelegramReply(chat_id=chat_id, text="Available doctors:", reply_markup=inline_keyboard(rows))]

    async def _specialization(self, chat_id: str, query: str) -> List[TelegramReply]:
        doctors = await self.service.list_doctors(specialization=query)
        if not doctors:
            return [TelegramReply(chat_id=chat_id, text=f"No active doctors matched “{query}”. Try a broader term.")]
        rows = []
        for doctor in doctors[:20]:
            profile = await self.engine.find_one(
                DoctorProfileModel, DoctorProfileModel.id == ObjectId(doctor.profile_id)
            )
            if profile:
                rows.append([(f"{doctor.name} — {doctor.specialization}", f"doctor:{profile.hospital_id}:{doctor.profile_id}")])
        return [TelegramReply(chat_id=chat_id, text=f"Doctors matching “{query}”:", reply_markup=inline_keyboard(rows))]

    async def _facility_reply(self, chat_id: str, hospital_id: str) -> TelegramReply:
        hospital = await self.service.get_hospital(hospital_id)
        facilities = "\n".join(f"• {item}" for item in hospital.facilities) or "• No facilities have been published yet."
        services = "\n".join(f"• {item}" for item in hospital.services) or "• No services have been published yet."
        return TelegramReply(chat_id=chat_id, text=f"🏥 {hospital.name}\n\nFacilities:\n{facilities}\n\nServices:\n{services}\n\nContact: {hospital.contact_number}")

    async def _doctor_reply(self, session: TelegramSessionModel, chat_id: str, hospital_id: str, doctor_id: str) -> TelegramReply:
        doctors = await self.service.list_doctors(hospital_id=hospital_id)
        doctor = next((item for item in doctors if item.profile_id == doctor_id), None)
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor is no longer available.")
        session.selected_hospital_id = hospital_id
        session.selected_doctor_id = doctor_id
        await save_session(self.engine, session)
        hours = ", ".join(f"{key}: {value}" for key, value in doctor.clinic_hours.items())
        return TelegramReply(
            chat_id=chat_id,
            text=f"👨‍⚕️ {doctor.name}\nSpecialization: {doctor.specialization}\nFee: {doctor.consultation_fee}\nHours: {hours}\nLanguages: {', '.join(doctor.languages_spoken) or 'Not listed'}",
            reply_markup=inline_keyboard([[('📅 Book appointment', f"book:{hospital_id}:{doctor_id}")]]),
        )

    async def _begin_booking(self, session: TelegramSessionModel, chat_id: str) -> List[TelegramReply]:
        if not await self._patient(session):
            return [self._registration_required(chat_id)]
        session.state = "book_date"
        session.booking_date = None
        session.booking_slot = None
        session.booking_reason = None
        session.booking_temperature = None
        session.booking_symptoms = []
        await save_session(self.engine, session)
        return [TelegramReply(chat_id=chat_id, text="Enter the appointment date in YYYY-MM-DD format. Bookings are available from today through 7 days ahead.")]

    async def _confirm_booking(self, session: TelegramSessionModel, chat_id: str) -> List[TelegramReply]:
        patient = await self._patient(session)
        if not patient:
            return [self._registration_required(chat_id)]
        request = BookAppointmentRequest(
            hospital_id=session.selected_hospital_id,
            doctor_id=session.selected_doctor_id,
            date=session.booking_date,
            slot=session.booking_slot,
            reason=session.booking_reason,
            temperature=session.booking_temperature,
            symptoms=session.booking_symptoms,
        )
        self._clear_workflow(session)
        await save_session(self.engine, session)
        appointment = await self.service.book(patient, request)
        return [TelegramReply(chat_id=chat_id, text=f"✅ Appointment booked for {appointment.date} at {appointment.slot}.\nStatus: {appointment.status}\nAppointment ID: {appointment.appointment_id}")]

    async def _appointments(self, session: TelegramSessionModel, chat_id: str) -> List[TelegramReply]:
        patient = await self._patient(session)
        if not patient:
            return [self._registration_required(chat_id)]
        appointments = await self.service.appointments(patient)
        if not appointments:
            return [TelegramReply(chat_id=chat_id, text="You do not have any appointments yet.")]
        lines = [f"• {item.date} at {item.slot} — {item.status}{' (cancelled)' if item.is_cancelled else ''}" for item in appointments[:20]]
        return [TelegramReply(chat_id=chat_id, text="Your appointments:\n" + "\n".join(lines))]

    async def _prescriptions(self, session: TelegramSessionModel, chat_id: str) -> List[TelegramReply]:
        patient = await self._patient(session)
        if not patient:
            return [self._registration_required(chat_id)]
        prescriptions = await self.service.prescriptions(patient)
        if not prescriptions:
            return [TelegramReply(chat_id=chat_id, text="No prescriptions are available in your account.")]
        replies = []
        for prescription in prescriptions[:10]:
            medicines = "\n".join(
                f"• {item.medicine_name}: {item.dosage}, {item.frequency}, {item.duration}"
                for item in prescription.medications
            ) or "• No medicines listed"
            replies.append(TelegramReply(chat_id=chat_id, text=f"📄 Prescription — {prescription.date}\nDoctor: {prescription.doctor_name}\nDiagnosis: {prescription.diagnosis}\nMedicines:\n{medicines}\nNotes: {prescription.notes or 'None'}\nFollow-up: {prescription.follow_up_date or 'Not specified'}"))
        return replies

    async def _link(self, session: TelegramSessionModel, code: str, chat_id: str) -> List[TelegramReply]:
        from telegram_bot.cruds import consume_link_code

        link = await consume_link_code(self.engine, hash_link_code(code))
        expires_at = link.expires_at if link else None
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if not link or not expires_at or expires_at <= datetime.now(timezone.utc):
            return [TelegramReply(chat_id=chat_id, text="That link code is invalid or expired. Generate a new one from your authenticated account.")]
        patient = await self.engine.find_one(UserModel, UserModel.id == ObjectId(link.patient_id))
        if not patient or patient.role != UserRole.PATIENT:
            return [TelegramReply(chat_id=chat_id, text="Only patient accounts can be linked to this bot.")]
        if patient.telegram_user_id and patient.telegram_user_id != session.telegram_user_id:
            return [TelegramReply(chat_id=chat_id, text="That patient account is already linked to another Telegram user.")]
        existing = await find_user_by_telegram_id(self.engine, session.telegram_user_id)
        if existing and str(existing.id) != str(patient.id):
            return [TelegramReply(chat_id=chat_id, text="This Telegram user is already linked to another patient account.")]
        await link_user_to_telegram(self.engine, patient, session.telegram_user_id)
        session.patient_id = str(patient.id)
        session.state = "idle"
        await save_session(self.engine, session)
        return [TelegramReply(chat_id=chat_id, text=f"✅ Linked securely. Welcome, {patient.name}.")]

    async def _state_register_name(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        if len(text.strip()) < 2:
            return [TelegramReply(chat_id=chat_id, text="Please enter your full name (at least 2 characters).")]
        session.pending_name = text.strip()
        session.state = "register_email"
        await save_session(self.engine, session)
        return [TelegramReply(chat_id=chat_id, text="What is your email address?")]

    async def _state_register_email(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        try:
            email = str(EMAIL_ADAPTER.validate_python(text)).lower()
        except ValidationError:
            return [TelegramReply(chat_id=chat_id, text="Please enter a valid email address.")]
        session.pending_email = email
        session.state = "register_phone"
        await save_session(self.engine, session)
        return [TelegramReply(chat_id=chat_id, text="Enter your phone number, including country code (for example +919876543210). Do not send a password in Telegram.")]

    async def _state_register_phone(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        if not PHONE_PATTERN.fullmatch(text):
            return [TelegramReply(chat_id=chat_id, text="Please enter a valid phone number including country code.")]
        patient = await self.service.register_patient(session.pending_name or "Patient", session.pending_email or "", text, session.telegram_user_id)
        session.patient_id = str(patient.id)
        session.pending_name = None
        session.pending_email = None
        session.state = "idle"
        await save_session(self.engine, session)
        return [TelegramReply(chat_id=chat_id, text=f"✅ Registration complete. Welcome, {patient.name}. You can now book appointments and view your private records.")]

    async def _state_link_code(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        return await self._link(session, text, chat_id)

    async def _state_specialization(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        session.state = "idle"
        await save_session(self.engine, session)
        return await self._specialization(chat_id, text)

    async def _state_book_date(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        slots = await self.service.available_slots(session.selected_hospital_id or "", session.selected_doctor_id or "", text)
        if not slots.available_slots:
            return [TelegramReply(chat_id=chat_id, text="No slots are available on that date. Please enter another date.")]
        session.booking_date = text
        session.state = "book_slot"
        await save_session(self.engine, session)
        rows = [[(slot, f"slot:{slot}") for slot in slots.available_slots[index:index + 3]] for index in range(0, len(slots.available_slots), 3)]
        return [TelegramReply(chat_id=chat_id, text="Choose an available time:", reply_markup=inline_keyboard(rows))]

    async def _state_book_reason(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        if len(text.strip()) < 10:
            return [TelegramReply(chat_id=chat_id, text="Please describe the reason in at least 10 characters.")]
        session.booking_reason = text.strip()
        session.state = "book_temperature"
        await save_session(self.engine, session)
        return [TelegramReply(chat_id=chat_id, text="What is the patient's current temperature in °F? Enter a number from 95 to 110.")]

    async def _state_book_temperature(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        try:
            temperature = float(text)
        except ValueError:
            temperature = 0
        if temperature < 95 or temperature > 110:
            return [TelegramReply(chat_id=chat_id, text="Enter a valid temperature between 95 and 110 °F.")]
        session.booking_temperature = temperature
        session.state = "book_symptoms"
        await save_session(self.engine, session)
        return [TelegramReply(chat_id=chat_id, text="List one or more symptoms separated by commas: fever, cough, cold, bodyache, headache, other.")]

    async def _state_book_symptoms(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        symptoms = [item.strip().casefold() for item in text.split(",") if item.strip()]
        allowed = {item.value for item in Symptom}
        invalid = [item for item in symptoms if item not in allowed]
        if not symptoms or invalid:
            return [TelegramReply(chat_id=chat_id, text=f"Use only: {', '.join(sorted(allowed))}.")]
        session.booking_symptoms = list(dict.fromkeys(symptoms))
        session.state = "book_confirm"
        await save_session(self.engine, session)
        summary = f"Confirm appointment:\nDate: {session.booking_date}\nTime: {session.booking_slot}\nReason: {session.booking_reason}\nTemperature: {session.booking_temperature} °F\nSymptoms: {', '.join(session.booking_symptoms)}"
        return [TelegramReply(chat_id=chat_id, text=summary, reply_markup=inline_keyboard([[('✅ Confirm booking', 'confirm_booking'), ('❌ Cancel', 'cancel_booking')]]))]

    @staticmethod
    def _clear_workflow(session: TelegramSessionModel) -> None:
        session.state = "idle"
        session.booking_date = None
        session.booking_slot = None
        session.booking_reason = None
        session.booking_temperature = None
        session.booking_symptoms = []
        session.pending_name = None
        session.pending_email = None
