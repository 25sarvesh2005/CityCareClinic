"""Hermes-inspired Telegram message gateway and patient workflow state machine."""

import asyncio
import hashlib
import json
import logging
import re
import weakref
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException
from odmantic import AIOEngine
from odmantic.exceptions import DuplicateKeyError as ODManticDuplicateKeyError
from pydantic import EmailStr, TypeAdapter, ValidationError

from chatbot.prescription_assistant import is_emergency_message
from core.apis.schemas.appointment_schema import BookAppointmentRequest
from core.constants import UserRole
from core.cruds.user_crud import (
    find_user_by_telegram_id,
    link_user_to_telegram,
)
from core.models.doctor_profile_model import DoctorProfileModel
from core.models.user_model import UserModel
from telegram_bot.cruds import (
    add_message,
    claim_update,
    clear_messages,
    get_or_create_session,
    mark_update_delivered,
    recent_messages,
    save_session,
    store_update_replies,
)
from telegram_bot.conversation import (
    NaturalIntent,
    choice_index,
    detect_intent,
    is_affirmative,
    is_cancel_message,
    is_negative,
    parse_natural_date,
    parse_natural_time,
    parse_symptoms,
    parse_temperature,
)
from telegram_bot.medical_assistant import resolve_patient_message
from telegram_bot.models import TelegramSessionModel, TelegramUpdateModel
from telegram_bot.patient_service import TelegramPatientService
from telegram_bot.schemas import TelegramDispatch, TelegramReply


EMAIL_ADAPTER = TypeAdapter(EmailStr)
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 -]{6,18}[0-9]$")
LOGGER = logging.getLogger(__name__)


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


def _explicit_booking_time(text: str) -> Optional[str]:
    """Extract a time only when the message clearly presents one as a time."""
    if not re.search(
        r"\b(?:at\s+|for\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|"
        r"\b(?:noon|midnight)\b|\b\d{1,2}:\d{2}\b",
        text.casefold(),
    ):
        return None
    return parse_natural_time(text)


def _explicit_booking_temperature(text: str) -> Optional[float]:
    """Avoid confusing dates, times, or durations with body temperature."""
    match = re.search(
        r"(?:\btemp(?:erature)?\b\s*(?:is|of|=|:)?\s*\d{2,3}(?:\.\d+)?\s*°?\s*[fc]?\b|"
        r"\b\d{2,3}(?:\.\d+)?\s*°\s*[fc]\b|"
        r"\b\d{2,3}(?:\.\d+)?\s+[fc]\b)",
        text.casefold(),
    )
    return parse_temperature(match.group(0)) if match else None


def _combined_booking_reason(text: str) -> Optional[str]:
    """Extract a visit reason from a message that may also contain logistics."""
    normalized = re.sub(r"\s+", " ", text.strip())
    reason_text = re.sub(
        r"\b(?:at|for)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)\b",
        " ",
        normalized,
        flags=re.IGNORECASE,
    )
    candidates = []
    for match in re.finditer(
        r"\b(?:reason(?:\s+is)?|because(?:\s+of)?|due\s+to|for)\s+(.+)",
        reason_text,
        flags=re.IGNORECASE,
    ):
        candidate = match.group(1).strip(" ,.-")
        if re.match(r"\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", candidate, re.IGNORECASE):
            continue
        candidate = re.split(
            r"[,;]?\s*\b(?:with\s+)?(?:a\s+)?temp(?:erature)?\b",
            candidate,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" ,.-")
        if len(candidate) >= 10:
            candidates.append(candidate)
    if candidates:
        return candidates[0]

    if re.search(
        r"\b(pain|ache|fever|cough|cold|rash|dizz|nause|vomit|breath|"
        r"sick|unwell|checkup|check-up|consultation|injury|symptom)\b",
        normalized,
        flags=re.IGNORECASE,
    ) and len(normalized) >= 10:
        return normalized
    return None


def _combined_booking_symptoms(text: str) -> List[str]:
    """Infer symptoms only when health language is actually present."""
    if not re.search(
        r"\b(pain|ache|fever|cough|cold|rash|dizz|nause|vomit|breath|"
        r"sick|unwell|injury|symptom|head|body|stomach|throat)\b",
        text,
        flags=re.IGNORECASE,
    ):
        return []
    return parse_symptoms(text)


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
        callback_query_id = (update.get("callback_query") or {}).get("id")
        normalized = self._normalize(update)
        chat_id = normalized[1] if normalized else "unknown"
        claimed, ledger = await claim_update(self.engine, update_id, chat_id)
        if not claimed:
            return self._replay_dispatch(ledger, callback_query_id)

        if not normalized:
            dispatch = TelegramDispatch(update_id=update_id)
            await store_update_replies(self.engine, update_id, "unknown", "[]")
            return dispatch

        user_id, chat_id, chat_type, username, text = normalized
        if chat_type != "private":
            replies = [
                TelegramReply(
                    chat_id=chat_id,
                    text="For privacy, the Medihub patient assistant works only in a private chat. Please message the bot directly.",
                )
            ]
            await store_update_replies(
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
            except Exception:
                LOGGER.exception("Telegram update %s failed during processing", update_id)
                replies = [
                    TelegramReply(
                        chat_id=chat_id,
                        text="Something went wrong while processing that request. Please try again with a new message.",
                    )
                ]

            replies_json = json.dumps(
                [reply.model_dump(exclude_none=True) for reply in replies]
            )
            await store_update_replies(self.engine, update_id, chat_id, replies_json)
            return TelegramDispatch(
                update_id=update_id,
                replies=replies,
                callback_query_id=callback_query_id,
            )

    @staticmethod
    def _replay_dispatch(
        recorded: TelegramUpdateModel, callback_query_id: Optional[str]
    ) -> TelegramDispatch:
        """Recreate a safe dispatch from a durable claim or completed ledger row."""
        in_progress = recorded.status == "processing" and not recorded.delivered
        replies = []
        if not recorded.delivered and not in_progress:
            replies = [
                TelegramReply.model_validate(item)
                for item in json.loads(recorded.replies_json)
            ]
        return TelegramDispatch(
            update_id=recorded.update_id,
            replies=replies,
            replayed=True,
            in_progress=in_progress,
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
            return await self._begin_registration(session, chat_id)
        if command == "/link":
            if await self._patient(session):
                return [TelegramReply(chat_id=chat_id, text="This Telegram account is already linked.")]
            if argument.strip():
                return await self._link(session, argument.strip(), chat_id)
            return await self._begin_linking(session, chat_id)
        if command == "/hospitals":
            return await self._hospitals(session, chat_id)
        if command == "/doctors":
            return await self._doctors(session, chat_id, session.selected_hospital_id)
        if command in {"/speciality", "/specialization"}:
            if argument.strip():
                return await self._specialization(session, chat_id, argument.strip())
            session.state = "specialization"
            await save_session(self.engine, session)
            return [TelegramReply(chat_id=chat_id, text="Which specialization are you looking for? For example: cardiologist or general physician.")]
        if command == "/facilities":
            if session.selected_hospital_id:
                return [await self._facility_reply(chat_id, session.selected_hospital_id)]
            return await self._hospital_choices(session, chat_id, "Which hospital's facilities would you like to see?", "facilities")
        if command == "/book":
            if not await self._patient(session):
                return [self._registration_required(chat_id)]
            if session.selected_hospital_id and session.selected_doctor_id:
                return await self._begin_booking(session, chat_id)
            return await self._hospital_choices(session, chat_id, "Which hospital would you like to book at?", "doctors")
        if command == "/appointments":
            return await self._appointments(session, chat_id)
        if command == "/prescriptions":
            return await self._prescriptions(session, chat_id)

        if session.state != "idle" and is_cancel_message(text):
            self._clear_workflow(session)
            await save_session(self.engine, session)
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text="No problem - I cancelled that step. What would you like help with instead?",
                )
            ]

        if text == "menu:hospitals":
            return await self._hospitals(session, chat_id)
        if text == "menu:doctors":
            return await self._doctors(session, chat_id, session.selected_hospital_id)
        if text == "start_register":
            return await self._begin_registration(session, chat_id)
        if text == "start_link":
            return await self._begin_linking(session, chat_id)

        if text.startswith("hospital:"):
            hospital_id = text.split(":", 1)[1]
            session.selected_hospital_id = hospital_id
            session.selected_doctor_id = None
            session.state = "idle"
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
            return await self._doctors(session, chat_id, text.split(":", 1)[1])
        if text.startswith("facilities:"):
            session.selected_hospital_id = text.split(":", 1)[1]
            session.state = "idle"
            await save_session(self.engine, session)
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
            return await self._consume_booking_details(session, "", chat_id)
        if text == "confirm_booking" and session.state == "book_confirm":
            return await self._confirm_booking(session, chat_id)
        if text == "cancel_booking":
            self._clear_workflow(session)
            await save_session(self.engine, session)
            return [TelegramReply(chat_id=chat_id, text="Booking cancelled. No appointment was created.")]

        state_handler = getattr(self, f"_state_{session.state}", None)
        if state_handler:
            return await state_handler(session, text, chat_id)

        # Emergencies always stay on the fixed safety path, even if the message also
        # contains words such as "doctor" or "appointment".
        if is_emergency_message(text):
            return await self._medical_conversation(session, text, chat_id)

        intent = detect_intent(text)
        if intent:
            replies = await self._handle_natural_intent(session, intent, chat_id)
            await self._remember_exchange(session, text, replies)
            return replies

        return await self._medical_conversation(session, text, chat_id)

    async def _medical_conversation(
        self, session: TelegramSessionModel, text: str, chat_id: str
    ) -> List[TelegramReply]:
        """Resolve a contextual turn, then execute verified operations in the gateway."""
        history = [
            {"role": item.role, "content": item.content}
            for item in await recent_messages(self.engine, str(session.id))
        ]
        decision = await resolve_patient_message(text, history)
        if decision.intent not in {"medical_chat", "greeting", "help"}:
            replies = await self._handle_natural_intent(
                session,
                NaturalIntent(
                    decision.intent,
                    specialization=decision.specialization,
                ),
                chat_id,
            )
            if replies:
                await self._remember_exchange(session, text, replies)
                return replies

        answer = decision.reply or (
            "I can help with your health concern, doctors, appointments, facilities, "
            "registration, and patient records. What would you like to do?"
        )
        await add_message(self.engine, str(session.id), "user", text)
        await add_message(self.engine, str(session.id), "assistant", answer)
        return [TelegramReply(chat_id=chat_id, text=answer)]

    async def _remember_exchange(
        self,
        session: TelegramSessionModel,
        user_text: str,
        replies: List[TelegramReply],
    ) -> None:
        """Keep natural action turns in the same short-term memory as health chat."""
        await add_message(self.engine, str(session.id), "user", user_text)
        response_text = "\n\n".join(reply.text for reply in replies if reply.text)
        if response_text:
            await add_message(self.engine, str(session.id), "assistant", response_text)

    async def _handle_natural_intent(
        self,
        session: TelegramSessionModel,
        intent: NaturalIntent,
        chat_id: str,
    ) -> List[TelegramReply]:
        """Route inferred actions through the same patient-safe gateway methods."""
        if intent.name in {"greeting", "help"}:
            return [self._welcome(session, chat_id)]
        if intent.name == "account_status":
            return await self._account_status(session, chat_id)
        if intent.name == "register":
            return await self._begin_registration(session, chat_id)
        if intent.name == "link":
            return await self._begin_linking(session, chat_id)
        if intent.name == "hospitals":
            return await self._hospitals(session, chat_id)
        if intent.name == "doctors":
            return await self._doctors(session, chat_id, session.selected_hospital_id)
        if intent.name == "specialization":
            return await self._specialization(
                session, chat_id, intent.specialization or ""
            )
        if intent.name == "facilities":
            if session.selected_hospital_id:
                return [
                    await self._facility_reply(chat_id, session.selected_hospital_id)
                ]
            return await self._hospital_choices(
                session,
                chat_id,
                "Sure - which hospital's facilities or services should I show?",
                "facilities",
            )
        if intent.name == "book":
            if not await self._patient(session):
                return [self._registration_required(chat_id)]
            if intent.specialization:
                return await self._specialization(
                    session, chat_id, intent.specialization
                )
            if session.selected_hospital_id and session.selected_doctor_id:
                return await self._begin_booking(session, chat_id)
            return await self._hospital_choices(
                session,
                chat_id,
                "Let's book it. Which hospital would you prefer?",
                "doctors",
            )
        if intent.name == "appointments":
            return await self._appointments(session, chat_id)
        if intent.name == "appointment_status":
            return await self._appointments(session, chat_id, focus_status=True)
        if intent.name == "prescriptions":
            return await self._prescriptions(session, chat_id)
        return []

    async def _account_status(
        self, session: TelegramSessionModel, chat_id: str
    ) -> List[TelegramReply]:
        """Explain verified registration/link status in ordinary patient language."""
        patient = await self._patient(session)
        if patient:
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text=(
                        f"Yes - your registration is complete, {patient.name}. "
                        "This Telegram account is linked to your Medihub patient profile, "
                        "so you can book appointments and view your private records here."
                    ),
                )
            ]
        return [
            TelegramReply(
                chat_id=chat_id,
                text=(
                    "I don't see a Medihub patient profile linked to this Telegram account yet. "
                    "If you already registered on the web portal, link that account; otherwise, "
                    "you can register here."
                ),
                reply_markup=inline_keyboard(
                    [[("Register here", "start_register"), ("Link account", "start_link")]]
                ),
            )
        ]

    async def _begin_registration(
        self, session: TelegramSessionModel, chat_id: str
    ) -> List[TelegramReply]:
        if await self._patient(session):
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text="You're already registered and your patient account is linked.",
                )
            ]
        self._clear_workflow(session)
        session.state = "register_name"
        await save_session(self.engine, session)
        return [
            TelegramReply(
                chat_id=chat_id,
                text="Absolutely - I can register you here. First, what's your full name?",
            )
        ]

    async def _begin_linking(
        self, session: TelegramSessionModel, chat_id: str
    ) -> List[TelegramReply]:
        if await self._patient(session):
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text="Your Telegram account is already linked to a patient account.",
                )
            ]
        self._clear_workflow(session)
        session.state = "link_code"
        await save_session(self.engine, session)
        return [
            TelegramReply(
                chat_id=chat_id,
                text="Send me the one-time link code from your Medihub patient account.",
            )
        ]

    def _welcome(self, session: TelegramSessionModel, chat_id: str) -> TelegramReply:
        linked = bool(session.patient_id)
        identity = "✅ Patient account linked" if linked else "ℹ️ Not registered yet — use /register or /link"
        return TelegramReply(
            chat_id=chat_id,
            text=(
                "Hi! I'm the Medihub Patient Assistant.\n"
                f"{identity}\n\n"
                "Talk to me normally - for example: 'I have had a headache since "
                "yesterday', 'find me a skin doctor', or 'book an appointment'.\n\n"
                "If you prefer commands, use:\n"
                "/hospitals — hospital list\n/doctors — available doctors\n"
                "/speciality — find a specialist\n/book — book an appointment\n"
                "/facilities — hospital services\n/appointments — your appointments\n"
                "/prescriptions — your prescriptions\n/reset — reset this conversation\n\n"
                "This assistant provides general guidance, not a diagnosis. "
                "For an emergency, call local emergency services now."
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
            text=(
                "Registration is required for private patient operations. "
                "I can do that once I know which patient account is yours. "
                "Would you like to register here or link your existing Medihub account?"
            ),
            reply_markup=inline_keyboard(
                [[("Register here", "start_register"), ("Link account", "start_link")]]
            ),
        )

    async def _hospital_choices(
        self,
        session: TelegramSessionModel,
        chat_id: str,
        heading: str,
        action: str,
    ) -> List[TelegramReply]:
        hospitals = await self.service.list_hospitals()
        if not hospitals:
            return [TelegramReply(chat_id=chat_id, text="I couldn't find any active hospitals right now.")]
        session.state = f"choose_hospital_{action}"
        await save_session(self.engine, session)
        visible = hospitals[:20]
        rows = [[(f"{item.name} - {item.city}", f"{action}:{item.hospital_id}")] for item in visible]
        numbered = "\n".join(
            f"{index}. {item.name} - {item.city}"
            for index, item in enumerate(visible, start=1)
        )
        return [
            TelegramReply(
                chat_id=chat_id,
                text=f"{heading}\n\n{numbered}\n\nReply with the name or number, or tap a button.",
                reply_markup=inline_keyboard(rows),
            )
        ]

    async def _hospitals(self, session: TelegramSessionModel, chat_id: str) -> List[TelegramReply]:
        return await self._hospital_choices(
            session, chat_id, "Here are the available hospitals:", "hospital"
        )

    async def _doctors(
        self, session: TelegramSessionModel, chat_id: str, hospital_id: Optional[str]
    ) -> List[TelegramReply]:
        if not hospital_id:
            return await self._hospital_choices(
                session, chat_id, "Which hospital should I check for doctors?", "doctors"
            )
        doctors = await self.service.list_doctors(hospital_id=hospital_id)
        if not doctors:
            return [TelegramReply(chat_id=chat_id, text="I couldn't find any active doctors at that hospital right now.")]
        session.selected_hospital_id = hospital_id
        session.state = "choose_doctor"
        await save_session(self.engine, session)
        visible = doctors[:20]
        rows = [[(f"{doctor.name} - {doctor.specialization}", f"doctor:{hospital_id}:{doctor.profile_id}")] for doctor in visible]
        numbered = "\n".join(
            f"{index}. {doctor.name} - {doctor.specialization}"
            for index, doctor in enumerate(visible, start=1)
        )
        return [
            TelegramReply(
                chat_id=chat_id,
                text=f"These doctors are available:\n\n{numbered}\n\nTell me the doctor's name or number to see details.",
                reply_markup=inline_keyboard(rows),
            )
        ]

    async def _specialization(
        self, session: TelegramSessionModel, chat_id: str, query: str
    ) -> List[TelegramReply]:
        doctors = await self.service.list_doctors(specialization=query)
        if not doctors:
            return [TelegramReply(chat_id=chat_id, text=f"I couldn't find an active specialist matching '{query}'. Try a broader specialty or describe your concern.")]
        session.last_specialization_query = query
        session.state = "choose_specialist"
        await save_session(self.engine, session)
        rows = []
        numbered = []
        for index, doctor in enumerate(doctors[:20], start=1):
            profile = await self.engine.find_one(
                DoctorProfileModel, DoctorProfileModel.id == ObjectId(doctor.profile_id)
            )
            if profile:
                rows.append([(f"{doctor.name} - {doctor.specialization}", f"doctor:{profile.hospital_id}:{doctor.profile_id}")])
                numbered.append(f"{index}. {doctor.name} - {doctor.specialization}")
        return [
            TelegramReply(
                chat_id=chat_id,
                text=f"I found these doctors for '{query}':\n\n" + "\n".join(numbered) + "\n\nReply with a doctor's name or number, or tap one below.",
                reply_markup=inline_keyboard(rows),
            )
        ]

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
        session.state = "idle"
        session.last_specialization_query = None
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
        return [
            TelegramReply(
                chat_id=chat_id,
                text=(
                    "Great - what day works for you? You can say today, tomorrow, "
                    "a weekday, or a date such as 2026-08-28. Bookings are available "
                    "through 7 days ahead."
                ),
            )
        ]

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
        appointment = await self.service.book(patient, request)
        self._clear_workflow(session)
        await save_session(self.engine, session)
        return [TelegramReply(chat_id=chat_id, text=f"✅ Appointment booked for {appointment.date} at {appointment.slot}.\nStatus: {appointment.status}\nAppointment ID: {appointment.appointment_id}")]

    async def _appointments(
        self,
        session: TelegramSessionModel,
        chat_id: str,
        *,
        focus_status: bool = False,
    ) -> List[TelegramReply]:
        patient = await self._patient(session)
        if not patient:
            return [self._registration_required(chat_id)]
        appointments = await self.service.appointments(patient)
        if not appointments:
            text = (
                "You do not have an appointment request to check yet."
                if focus_status
                else "You do not have any appointments yet."
            )
            return [TelegramReply(chat_id=chat_id, text=text)]

        def status_value(item) -> str:
            if item.is_cancelled:
                return "cancelled"
            value = item.status.value if hasattr(item.status, "value") else item.status
            return str(value or "pending").casefold()

        descriptions = {
            "pending": "pending — waiting for the doctor's approval",
            "accepted": "approved and accepted by the doctor",
            "rejected": "not approved; the doctor rejected the request",
            "completed": "completed",
            "cancelled": "cancelled",
        }
        if focus_status:
            latest = appointments[0]
            status = status_value(latest)
            detail = descriptions.get(status, status)
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text=(
                        f"Your latest appointment request for {latest.date} at "
                        f"{latest.slot} is {detail}."
                    ),
                )
            ]

        lines = [
            f"• {item.date} at {item.slot} — "
            f"{descriptions.get(status_value(item), status_value(item))}"
            for item in appointments[:20]
        ]
        return [TelegramReply(chat_id=chat_id, text="Your appointments:\n" + "\n".join(lines))]

    async def _prescriptions(self, session: TelegramSessionModel, chat_id: str) -> List[TelegramReply]:
        patient = await self._patient(session)
        if not patient:
            return [self._registration_required(chat_id)]
        prescriptions = await self.service.prescriptions(patient)
        if not prescriptions:
            appointments = await self.service.appointments(patient)
            status_values = [
                str(item.status.value if hasattr(item.status, "value") else item.status).casefold()
                for item in appointments
                if not item.is_cancelled
            ]
            accepted_count = status_values.count("accepted")
            pending_count = status_values.count("pending")
            completed_count = status_values.count("completed")

            if completed_count:
                explanation = (
                    f"I found {completed_count} completed visit"
                    f"{'s' if completed_count != 1 else ''}, but no prescription was "
                    "submitted to your Medihub account. If the doctor gave you one during "
                    "the consultation, please ask the hospital to upload or attach it to your record."
                )
            elif accepted_count:
                explanation = (
                    f"I can see {accepted_count} accepted appointment"
                    f"{'s' if accepted_count != 1 else ''}, but the doctor hasn't submitted "
                    "a prescription for them yet. Accepted means the appointment was approved; "
                    "a prescription appears only after the consultation when the doctor creates one. "
                    "If your visit already happened, please contact the hospital or doctor and ask "
                    "them to complete the consultation record."
                )
            elif pending_count:
                explanation = (
                    f"I found {pending_count} appointment request"
                    f"{'s' if pending_count != 1 else ''} still waiting for approval, and there "
                    "is no prescription yet. A doctor can add one after an accepted consultation."
                )
            elif appointments:
                explanation = (
                    "I found appointment history in your account, but no completed consultation "
                    "with a prescription. Cancelled or rejected appointments do not produce one."
                )
            else:
                explanation = (
                    "I checked the Medihub account linked to this Telegram chat, but it has no "
                    "appointments or prescriptions yet. If your previous visit used another account, "
                    "please ask the hospital to verify which patient profile contains that visit."
                )
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text=f"I checked your linked account, {patient.name}. {explanation}",
                )
            ]
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
        try:
            await link_user_to_telegram(self.engine, patient, session.telegram_user_id)
        except ODManticDuplicateKeyError:
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text="That patient account or Telegram identity was linked by another request. Generate a new code and check the linked account.",
                )
            ]
        session.patient_id = str(patient.id)
        session.state = "idle"
        await save_session(self.engine, session)
        return [TelegramReply(chat_id=chat_id, text=f"✅ Linked securely. Welcome, {patient.name}.")]

    async def _resolve_hospital_choice(self, text: str):
        hospitals = (await self.service.list_hospitals())[:20]
        selected_index = choice_index(text, hospitals)
        if selected_index is not None:
            return hospitals[selected_index]
        query = re.sub(
            r"\b(i choose|choose|select|hospital|clinic|number|option)\b",
            " ",
            text.casefold(),
        )
        query = re.sub(r"\s+", " ", query).strip()
        if not query:
            return None
        exact = [item for item in hospitals if item.name.casefold() == query]
        if len(exact) == 1:
            return exact[0]
        matches = [
            item
            for item in hospitals
            if query in item.name.casefold()
            or query in item.city.casefold()
            or item.name.casefold() in query
        ]
        return matches[0] if len(matches) == 1 else None

    async def _state_choose_hospital_hospital(
        self, session: TelegramSessionModel, text: str, chat_id: str
    ) -> List[TelegramReply]:
        hospital = await self._resolve_hospital_choice(text)
        if not hospital:
            return await self._hospital_choices(
                session,
                chat_id,
                "I couldn't tell which hospital you meant. Please use its name or number:",
                "hospital",
            )
        session.selected_hospital_id = hospital.hospital_id
        session.selected_doctor_id = None
        session.state = "idle"
        await save_session(self.engine, session)
        return [
            TelegramReply(
                chat_id=chat_id,
                text=f"🏥 {hospital.name}\n{hospital.address}, {hospital.city}\nContact: {hospital.contact_number}",
                reply_markup=inline_keyboard(
                    [[
                        ("Doctors", f"doctors:{hospital.hospital_id}"),
                        ("Facilities", f"facilities:{hospital.hospital_id}"),
                    ]]
                ),
            )
        ]

    async def _state_choose_hospital_doctors(
        self, session: TelegramSessionModel, text: str, chat_id: str
    ) -> List[TelegramReply]:
        hospital = await self._resolve_hospital_choice(text)
        if not hospital:
            return await self._hospital_choices(
                session,
                chat_id,
                "I couldn't tell which hospital you meant. Please use its name or number:",
                "doctors",
            )
        return await self._doctors(session, chat_id, hospital.hospital_id)

    async def _state_choose_hospital_facilities(
        self, session: TelegramSessionModel, text: str, chat_id: str
    ) -> List[TelegramReply]:
        hospital = await self._resolve_hospital_choice(text)
        if not hospital:
            return await self._hospital_choices(
                session,
                chat_id,
                "I couldn't tell which hospital you meant. Please use its name or number:",
                "facilities",
            )
        session.selected_hospital_id = hospital.hospital_id
        session.state = "idle"
        await save_session(self.engine, session)
        return [await self._facility_reply(chat_id, hospital.hospital_id)]

    async def _resolve_doctor_choice(
        self,
        session: TelegramSessionModel,
        text: str,
        chat_id: str,
        *,
        specialization: Optional[str] = None,
    ) -> List[TelegramReply]:
        doctors = (
            await self.service.list_doctors(
                hospital_id=None if specialization else session.selected_hospital_id,
                specialization=specialization or "",
            )
        )[:20]
        selected_index = choice_index(text, doctors)
        doctor = doctors[selected_index] if selected_index is not None else None
        if doctor is None:
            query = re.sub(
                r"\b(i choose|choose|select|doctor|dr|number|option)\b",
                " ",
                text.casefold(),
            )
            query = re.sub(r"\s+", " ", query).strip(" .")
            exact = [item for item in doctors if item.name.casefold().removeprefix("dr. ") == query]
            matches = exact or [
                item
                for item in doctors
                if query
                and (
                    query in item.name.casefold()
                    or item.name.casefold().removeprefix("dr. ") in query
                )
            ]
            doctor = matches[0] if len(matches) == 1 else None
        if doctor is None:
            if specialization:
                return await self._specialization(session, chat_id, specialization)
            return await self._doctors(
                session, chat_id, session.selected_hospital_id
            )

        hospital_id = session.selected_hospital_id
        if specialization:
            profile = await self.engine.find_one(
                DoctorProfileModel,
                DoctorProfileModel.id == ObjectId(doctor.profile_id),
            )
            hospital_id = profile.hospital_id if profile else None
        if not hospital_id:
            raise HTTPException(status_code=404, detail="Doctor's hospital is unavailable.")
        return [
            await self._doctor_reply(
                session, chat_id, str(hospital_id), doctor.profile_id
            )
        ]

    async def _state_choose_doctor(
        self, session: TelegramSessionModel, text: str, chat_id: str
    ) -> List[TelegramReply]:
        return await self._resolve_doctor_choice(session, text, chat_id)

    async def _state_choose_specialist(
        self, session: TelegramSessionModel, text: str, chat_id: str
    ) -> List[TelegramReply]:
        return await self._resolve_doctor_choice(
            session,
            text,
            chat_id,
            specialization=session.last_specialization_query or "",
        )

    async def _state_register_name(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        name = re.sub(
            r"^(?:my name is|i am|i'm|this is)\s+",
            "",
            text.strip(),
            flags=re.IGNORECASE,
        ).strip()
        if len(name) < 2:
            return [TelegramReply(chat_id=chat_id, text="Please enter your full name (at least 2 characters).")]
        session.pending_name = name
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
        code = re.sub(
            r"^(?:my )?(?:link )?code is\s+",
            "",
            text.strip(),
            flags=re.IGNORECASE,
        ).strip()
        return await self._link(session, code, chat_id)

    async def _state_specialization(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        session.state = "idle"
        await save_session(self.engine, session)
        inferred = detect_intent(f"find a {text} doctor")
        query = inferred.specialization if inferred and inferred.specialization else text
        return await self._specialization(session, chat_id, query)

    async def _state_book_date(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        return await self._consume_booking_details(session, text, chat_id)

    async def _state_book_slot(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        return await self._consume_booking_details(session, text, chat_id)

    async def _state_book_reason(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        return await self._consume_booking_details(session, text, chat_id)

    async def _state_book_temperature(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        return await self._consume_booking_details(session, text, chat_id)

    async def _state_book_symptoms(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        return await self._consume_booking_details(session, text, chat_id)

    async def _consume_booking_details(
        self, session: TelegramSessionModel, text: str, chat_id: str
    ) -> List[TelegramReply]:
        """Consume every booking detail present, then ask only for the first missing one."""
        incoming_state = session.state

        if not session.booking_date:
            session.booking_date = parse_natural_date(text)
        if not session.booking_slot:
            session.booking_slot = (
                parse_natural_time(text)
                if incoming_state == "book_slot"
                else _explicit_booking_time(text)
            )
        if not session.booking_reason:
            reason = (
                text.strip()
                if incoming_state == "book_reason" and len(text.strip()) >= 10
                else _combined_booking_reason(text)
            )
            session.booking_reason = reason
        if session.booking_temperature is None:
            temperature = (
                parse_temperature(text)
                if incoming_state == "book_temperature"
                else _explicit_booking_temperature(text)
            )
            if temperature is not None and 95 <= temperature <= 110:
                session.booking_temperature = temperature
        if not session.booking_symptoms:
            session.booking_symptoms = (
                parse_symptoms(text)
                if incoming_state == "book_symptoms"
                else _combined_booking_symptoms(text)
            )

        if not session.booking_date:
            session.state = "book_date"
            await save_session(self.engine, session)
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text="What day works for you? You can say 'tomorrow', a weekday, or YYYY-MM-DD.",
                )
            ]

        slots = await self.service.available_slots(
            session.selected_hospital_id or "",
            session.selected_doctor_id or "",
            session.booking_date,
        )
        if not slots.available_slots:
            session.booking_date = None
            session.booking_slot = None
            session.state = "book_date"
            await save_session(self.engine, session)
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text="No slots are available on that date. What other day would work?",
                )
            ]

        if session.booking_slot and session.booking_slot not in slots.available_slots:
            unavailable_slot = session.booking_slot
            session.booking_slot = None
            session.state = "book_slot"
            await save_session(self.engine, session)
            available = ", ".join(slots.available_slots)
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text=(
                        f"{unavailable_slot} isn't available on {session.booking_date}. "
                        f"Current options are: {available}."
                    ),
                )
            ]

        if not session.booking_slot:
            session.state = "book_slot"
            await save_session(self.engine, session)
            rows = [
                [(slot, f"slot:{slot}") for slot in slots.available_slots[index : index + 3]]
                for index in range(0, len(slots.available_slots), 3)
            ]
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text=(
                        f"I saved {session.booking_date}. What time would you prefer? "
                        "Type a time such as '10 am' or tap one:"
                    ),
                    reply_markup=inline_keyboard(rows),
                )
            ]

        if not session.booking_reason:
            session.state = "book_reason"
            await save_session(self.engine, session)
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text=(
                        f"I saved {session.booking_date} at {session.booking_slot}. "
                        "What would you like the doctor to help you with?"
                    ),
                )
            ]

        if session.booking_temperature is None:
            session.state = "book_temperature"
            await save_session(self.engine, session)
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text="What is the patient's current temperature? You can send °F or °C.",
                )
            ]

        if not session.booking_symptoms:
            session.state = "book_symptoms"
            await save_session(self.engine, session)
            return [
                TelegramReply(
                    chat_id=chat_id,
                    text="What symptoms are you experiencing? Describe them normally.",
                )
            ]

        session.state = "book_confirm"
        await save_session(self.engine, session)
        summary = (
            f"Confirm appointment:\nDate: {session.booking_date}\n"
            f"Time: {session.booking_slot}\nReason: {session.booking_reason}\n"
            f"Temperature: {session.booking_temperature} °F\n"
            f"Symptoms: {', '.join(session.booking_symptoms)}"
        )
        return [
            TelegramReply(
                chat_id=chat_id,
                text=summary + "\n\nReply 'yes' to book it or 'no' to cancel.",
                reply_markup=inline_keyboard(
                    [[("✅ Confirm booking", "confirm_booking"), ("❌ Cancel", "cancel_booking")]]
                ),
            )
        ]

    async def _state_book_confirm(self, session: TelegramSessionModel, text: str, chat_id: str) -> List[TelegramReply]:
        if is_affirmative(text):
            return await self._confirm_booking(session, chat_id)
        if is_negative(text) or is_cancel_message(text):
            self._clear_workflow(session)
            await save_session(self.engine, session)
            return [TelegramReply(chat_id=chat_id, text="No problem - I cancelled the booking and didn't create an appointment.")]
        return [TelegramReply(chat_id=chat_id, text="Please reply 'yes' to confirm the appointment or 'no' to cancel it.")]

    @staticmethod
    def _clear_workflow(session: TelegramSessionModel) -> None:
        session.state = "idle"
        session.booking_date = None
        session.booking_slot = None
        session.booking_reason = None
        session.booking_temperature = None
        session.booking_symptoms = []
        session.last_specialization_query = None
        session.pending_name = None
        session.pending_email = None
