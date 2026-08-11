"""
─────────────────────────────────────────────────────────────────────────────
File        : core/cruds/appointment_crud.py
Purpose     : Database operations for the appointments collection.

Responsibilities:
    - Create appointment documents
    - Retrieve appointments by patient, date, or ID
    - Perform soft-delete cancellation
    - Provide aggregate counts for the doctor's stats dashboard

Rules:
    - No business logic of any kind
    - No HTTPExceptions
    - No authentication or authorization
    - Only MongoDB operations via the ODMantic Engine

Used By:
    - core/controllers/appointment_controller.py
    - core/controllers/clinic_controller.py
    - core/controllers/doctor_controller.py

Returns:
    See individual function docstrings.

Raises:
    - Propagates raw exceptions to the calling controller
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import date, datetime, timezone
from typing import List, Optional

from bson import ObjectId
from odmantic import AIOEngine

from common.logger import get_logger
from core.models.appointment_model import AppointmentModel

# ─── Logger ───────────────────────────────────────────────────────────────────

logger = get_logger(__name__)


# ─── CRUD Functions ───────────────────────────────────────────────────────────


async def create_appointment(
    engine: AIOEngine, appointment: AppointmentModel
) -> AppointmentModel:
    """
    Persist a new AppointmentModel document to the appointments collection.

    The unique (date, slot) index enforces Gate 4 at the database level.
    Motor raises a DuplicateKeyError if the slot is already taken.

    Args:
        engine      (AIOEngine)        : The active ODMantic engine instance.
        appointment (AppointmentModel) : A fully constructed appointment document.

    Returns:
        AppointmentModel: The saved document with its generated _id populated.

    Raises:
        Exception: Propagates Motor DuplicateKeyError or any other write failure.
    """
    saved_appointment = await engine.save(appointment)
    logger.debug(
        "Appointment created — patient: %s, date: %s, slot: %s",
        appointment.patient_name,
        appointment.date,
        appointment.slot,
    )
    return saved_appointment


from collections import Counter
from core.constants import MAX_PATIENTS_PER_SLOT


async def count_active_appointments_for_slot(
    engine: AIOEngine,
    hospital_id: str,
    doctor_id: str,
    appointment_date: str,
    slot: str,
) -> int:
    """
    Count active (non-cancelled) appointments for a specific
    (hospital, doctor, date, slot) tuple.

    This is Gate 4's pre-check. The final enforcement is the 4-column
    unique index on the AppointmentModel collection.

    Args:
        engine           (AIOEngine): The active ODMantic engine instance.
        hospital_id      (str)      : Required tenant scope — never omit.
        doctor_id        (str)      : Required doctor scope — never omit.
        appointment_date (str)      : Date string in YYYY-MM-DD format.
        slot             (str)      : Slot string in HH:MM format.

    Returns:
        int: Number of active bookings for that (hospital, doctor, date, slot).
    """
    return await engine.count(
        AppointmentModel,
        (AppointmentModel.hospital_id == hospital_id)
        & (AppointmentModel.doctor_id == doctor_id)
        & (AppointmentModel.date == appointment_date)
        & (AppointmentModel.slot == slot)
        & (AppointmentModel.is_cancelled == False),
    )


async def count_patient_active_appointments_for_date(
    engine: AIOEngine,
    patient_id: str,
    appointment_date: str,
) -> int:
    """
    Count active (non-cancelled) appointments for a specific patient on a specific date
    across the platform.

    Args:
        engine           (AIOEngine): The active ODMantic engine instance.
        patient_id       (str)      : String ObjectId of the patient.
        appointment_date (str)      : Date string in YYYY-MM-DD format.

    Returns:
        int: Number of active bookings for that patient on that date across all clinics.
    """
    return await engine.count(
        AppointmentModel,
        (AppointmentModel.patient_id == patient_id)
        & (AppointmentModel.date == appointment_date)
        & (AppointmentModel.is_cancelled == False),
    )


async def find_booked_slots_by_date(
    engine: AIOEngine,
    hospital_id: str,
    doctor_id: str,
    appointment_date: str,
) -> List[str]:
    """
    Retrieve all slot strings for a given (hospital, doctor, date) that have
    reached maximum capacity.

    Used by the free-slots discovery endpoint to show which slots are available
    for a specific doctor at a specific hospital on a given date.

    Args:
        engine           (AIOEngine): The active ODMantic engine instance.
        hospital_id      (str)      : Required tenant scope — never omit.
        doctor_id        (str)      : Required doctor scope — never omit.
        appointment_date (str)      : Date string in YYYY-MM-DD format.

    Returns:
        List[str]: Slot strings that are fully booked for that (hospital, doctor, date).
    """
    appointments = await engine.find(
        AppointmentModel,
        (AppointmentModel.hospital_id == hospital_id)
        & (AppointmentModel.doctor_id == doctor_id)
        & (AppointmentModel.date == appointment_date)
        & (AppointmentModel.is_cancelled == False),
    )
    slot_counts = Counter(appointment.slot for appointment in appointments)
    full_slots = [slot for slot, count in slot_counts.items() if count >= MAX_PATIENTS_PER_SLOT]
    logger.debug(
        "Full slots (>= %d patients) for hospital '%s', doctor '%s' on %s: %s",
        MAX_PATIENTS_PER_SLOT,
        hospital_id,
        doctor_id,
        appointment_date,
        full_slots,
    )
    return full_slots


async def find_appointments_by_patient(
    engine: AIOEngine,
    hospital_id: str,
    patient_id: str,
) -> List[AppointmentModel]:
    """
    Retrieve all appointments belonging to a specific patient at a specific hospital.

    Args:
        engine      (AIOEngine): The active ODMantic engine instance.
        hospital_id (str)      : Required tenant scope — never omit.
        patient_id  (str)      : String ObjectId of the patient.

    Returns:
        List[AppointmentModel]: All appointments for the patient at this hospital,
                                sorted by created_at descending (newest first).

    Raises:
        Exception: Propagates any Motor or ODMantic read failure.
    """
    appointments = await engine.find(
        AppointmentModel,
        (AppointmentModel.hospital_id == hospital_id)
        & (AppointmentModel.patient_id == patient_id),
        sort=AppointmentModel.created_at.desc(),
    )
    logger.debug(
        "Patient '%s' appointments at hospital '%s' fetched: %d records",
        patient_id,
        hospital_id,
        len(appointments),
    )
    return list(appointments)


async def find_all_appointments_by_patient(
    engine: AIOEngine,
    patient_id: str,
) -> List[AppointmentModel]:
    """
    Retrieve ALL appointments for a patient across ALL hospital tenants.

    Used by GET /v1/my-appointments so a patient can see their full
    booking history regardless of which hospital they booked at.
    Unlike find_appointments_by_patient, this function is intentionally
    NOT scoped by hospital_id — the patient_id ownership check is the
    only filter applied.

    Args:
        engine     (AIOEngine): The active ODMantic engine instance.
        patient_id (str)      : String ObjectId of the patient.

    Returns:
        List[AppointmentModel]: All appointments for this patient across all
                                hospitals, sorted by created_at descending.
    """
    appointments = await engine.find(
        AppointmentModel,
        AppointmentModel.patient_id == patient_id,
        sort=AppointmentModel.created_at.desc(),
    )
    logger.debug(
        "All appointments for patient '%s' fetched: %d records",
        patient_id,
        len(appointments),
    )
    return list(appointments)


async def find_schedule_by_date(
    engine: AIOEngine,
    hospital_id: str,
    appointment_date: str,
    doctor_ids: Optional[List[str]] = None,
) -> List[AppointmentModel]:
    """
    Retrieve all appointments for a given hospital + date, ordered by slot time.
    Optionally filters by doctor_ids to enforce strict doctor data isolation.

    Args:
        engine           (AIOEngine)            : The active ODMantic engine instance.
        hospital_id      (str)                  : Required tenant scope — never omit.
        appointment_date (str)                  : Date string in YYYY-MM-DD format.
        doctor_ids       (Optional[List[str]])  : Optional list of doctor IDs to scope results.

    Returns:
        List[AppointmentModel]: Appointments matching criteria, sorted by slot.

    Raises:
        Exception: Propagates any Motor or ODMantic read failure.
    """
    query = (AppointmentModel.hospital_id == hospital_id) & (AppointmentModel.date == appointment_date)
    if doctor_ids:
        valid_ids = [d for d in doctor_ids if d]
        if valid_ids:
            query = query & (AppointmentModel.doctor_id.in_(valid_ids))

    appointments = await engine.find(
        AppointmentModel,
        query,
        sort=AppointmentModel.slot,
    )
    logger.debug(
        "Schedule for hospital '%s' on %s (doctor_ids: %s) fetched: %d appointments",
        hospital_id,
        appointment_date,
        doctor_ids,
        len(appointments),
    )
    return list(appointments)


async def count_today_appointments(
    engine: AIOEngine,
    hospital_id: str,
    today_date: str,
    doctor_ids: Optional[List[str]] = None,
) -> int:
    """
    Count active (non-cancelled) appointments scheduled for today at a specific hospital,
    optionally scoped to specific doctors.

    Args:
        engine      (AIOEngine): The active ODMantic engine instance.
        hospital_id (str)      : Required tenant scope — never omit.
        today_date  (str)      : Today's date in YYYY-MM-DD format.
        doctor_ids  (Optional[List[str]]): Optional doctor IDs to filter counts.

    Returns:
        int: Count of active appointments for today at that hospital.

    Raises:
        Exception: Propagates any Motor or ODMantic read failure.
    """
    query = (
        (AppointmentModel.hospital_id == hospital_id)
        & (AppointmentModel.date == today_date)
        & (AppointmentModel.is_cancelled == False)
    )
    if doctor_ids:
        valid_ids = [d for d in doctor_ids if d]
        if valid_ids:
            query = query & (AppointmentModel.doctor_id.in_(valid_ids))

    count = await engine.count(AppointmentModel, query)
    logger.debug(
        "Today's active appointment count for hospital '%s' (doctor_ids: %s): %d",
        hospital_id,
        doctor_ids,
        count,
    )
    return count


async def count_upcoming_appointments(
    engine: AIOEngine,
    hospital_id: str,
    today_date: str,
    doctor_ids: Optional[List[str]] = None,
) -> int:
    """
    Count active (non-cancelled) appointments scheduled for future dates at a specific hospital,
    optionally scoped to specific doctors.

    Args:
        engine      (AIOEngine): The active ODMantic engine instance.
        hospital_id (str)      : Required tenant scope — never omit.
        today_date  (str)      : Today's date in YYYY-MM-DD format (exclusive lower bound).
        doctor_ids  (Optional[List[str]]): Optional doctor IDs to filter counts.

    Returns:
        int: Count of active appointments after today at that hospital.

    Raises:
        Exception: Propagates any Motor or ODMantic read failure.
    """
    query = (
        (AppointmentModel.hospital_id == hospital_id)
        & (AppointmentModel.date > today_date)
        & (AppointmentModel.is_cancelled == False)
    )
    if doctor_ids:
        valid_ids = [d for d in doctor_ids if d]
        if valid_ids:
            query = query & (AppointmentModel.doctor_id.in_(valid_ids))

    count = await engine.count(AppointmentModel, query)
    logger.debug(
        "Upcoming active appointment count for hospital '%s' (doctor_ids: %s): %d",
        hospital_id,
        doctor_ids,
        count,
    )
    return count


async def count_unique_patients(
    engine: AIOEngine,
    hospital_id: Optional[str] = None,
    doctor_ids: Optional[List[str]] = None,
) -> int:
    """
    Count the number of unique patients who have booked appointments.
    Optionally filters by hospital_id and/or doctor_ids.

    Args:
        engine      (AIOEngine): The active ODMantic engine instance.
        hospital_id (Optional[str]): Optional tenant scope.
        doctor_ids  (Optional[List[str]]): Optional doctor IDs to filter unique patients.

    Returns:
        int: Count of unique patient IDs matching the filters.
    """
    query = {}
    if hospital_id:
        query["hospital_id"] = hospital_id
    if doctor_ids:
        valid_ids = [d for d in doctor_ids if d]
        if valid_ids:
            if len(valid_ids) == 1:
                query["doctor_id"] = valid_ids[0]
            else:
                query["doctor_id"] = {"$in": valid_ids}

    db = engine.database
    collection = db["appointments"]
    distinct_patients = await collection.distinct("patient_id", query)
    return len(distinct_patients)



async def find_appointment_by_id(
    engine: AIOEngine,
    appointment_id: str,
    hospital_id: Optional[str] = None,
) -> Optional[AppointmentModel]:
    """
    Retrieve a single appointment document by its ObjectId.

    Optionally scoped to a hospital_id if provided.

    Args:
        engine         (AIOEngine)          : The active ODMantic engine instance.
        appointment_id (str)                : String ObjectId of the appointment.
        hospital_id    (Optional[str])      : Optional tenant scope.

    Returns:
        Optional[AppointmentModel]: The matching document, or None.

    Raises:
        Exception: Propagates any Motor or ODMantic read failure.
    """
    try:
        object_id = ObjectId(appointment_id)
    except Exception:
        logger.warning("Invalid ObjectId format: %s", appointment_id)
        return None

    if hospital_id:
        appointment = await engine.find_one(
            AppointmentModel,
            (AppointmentModel.id == object_id)
            & (AppointmentModel.hospital_id == hospital_id),
        )
    else:
        appointment = await engine.find_one(
            AppointmentModel,
            AppointmentModel.id == object_id,
        )
    logger.debug(
        "Appointment lookup by id '%s' in hospital '%s' — found: %s",
        appointment_id,
        hospital_id,
        appointment is not None,
    )
    return appointment


async def find_appointment_by_patient_and_id(
    engine: AIOEngine,
    patient_id: str,
    appointment_id: str,
) -> Optional[AppointmentModel]:
    """
    Retrieve a single appointment by ObjectId, scoped to a specific patient.

    Used for cancellation: a patient provides only the appointment_id.
    This function verifies ownership (patient_id matches) without requiring
    the caller to know the hospital_id. The controller still checks
    appointment.patient_id == patient_id before allowing cancellation.

    Args:
        engine         (AIOEngine): The active ODMantic engine instance.
        patient_id     (str)      : String ObjectId of the owning patient.
        appointment_id (str)      : String ObjectId of the appointment.

    Returns:
        Optional[AppointmentModel]: The matching document if found and owned
                                    by this patient, else None.
    """
    try:
        object_id = ObjectId(appointment_id)
    except Exception:
        logger.warning("Invalid ObjectId format: %s", appointment_id)
        return None

    appointment = await engine.find_one(
        AppointmentModel,
        (AppointmentModel.id == object_id)
        & (AppointmentModel.patient_id == patient_id),
    )
    logger.debug(
        "Appointment lookup by id '%s' for patient '%s' — found: %s",
        appointment_id,
        patient_id,
        appointment is not None,
    )
    return appointment


async def cancel_appointment_by_id(
    engine: AIOEngine, appointment: AppointmentModel
) -> AppointmentModel:
    """
    Perform a soft-delete cancellation by setting is_cancelled to True.

    The document is updated in place and saved back to MongoDB.
    The slot is immediately freed for rebooking once is_cancelled is True.

    Args:
        engine      (AIOEngine)        : The active ODMantic engine instance.
        appointment (AppointmentModel) : The appointment document to cancel.

    Returns:
        AppointmentModel: The updated document with is_cancelled set to True.

    Raises:
        Exception: Propagates any Motor or ODMantic write failure.
    """
    appointment.is_cancelled = True
    updated_appointment = await engine.save(appointment)
    logger.debug(
        "Appointment '%s' cancelled — date: %s, slot: %s",
        str(appointment.id),
        appointment.date,
        appointment.slot,
    )
    return updated_appointment


async def count_all_appointments(engine: AIOEngine) -> int:
    """Count total appointments booked across all hospitals."""
    return await engine.count(AppointmentModel)


async def count_platform_active_appointments(engine: AIOEngine) -> int:
    """Count total non-cancelled appointments across all hospitals."""
    return await engine.count(
        AppointmentModel,
        AppointmentModel.is_cancelled == False,
    )


async def count_hospital_total_appointments(engine: AIOEngine, hospital_id: str) -> int:
    """Count total appointments booked at a specific hospital (including cancelled)."""
    return await engine.count(
        AppointmentModel,
        AppointmentModel.hospital_id == hospital_id,
    )

