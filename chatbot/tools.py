"""
chatbot/tools.py - Security-Critical Tool Dispatcher

Before executing ANY tool call Gemini requests, independently verify the
requested doctor_id is inside the authenticated user's authorized set:
- role == DOCTOR: authorized set is [self] only
- role == HOSPITAL_OWNER: authorized set is every doctor under their own hospital_id
NEVER trust a doctor_id Gemini returns as pre-authorized.
"""

from typing import Any, Dict, Set
from odmantic import AIOEngine

from common.logger import get_logger
from bson import ObjectId
from core.constants import UserRole
from core.cruds.doctor_profile_crud import (
    find_profile_by_user_and_hospital,
    find_profile_by_user_id,
    find_profiles_by_hospital,
)
from core.models.appointment_model import AppointmentModel
from core.models.user_model import UserModel


logger = get_logger(__name__)


async def get_authorized_doctor_ids(engine: AIOEngine, current_user: dict) -> Set[str]:
    """
    Computes the strict set of authorized doctor IDs for the current user.
    - Role DOCTOR: authorized set = { user_id, doctor_profile_id }
    - Role HOSPITAL_OWNER: authorized set = { all user_ids and profile_ids of doctors affiliated with current_user['hospital_id'] }
    """
    role = current_user.get("role")
    hospital_id = current_user.get("hospital_id")
    user_id = current_user.get("user_id")

    authorized_ids: Set[str] = set()

    if role == UserRole.DOCTOR.value:
        # Authorized set is ONLY self (user_id and doctor_profile_id)
        if user_id:
            authorized_ids.add(user_id)
        if hospital_id and user_id:
            profile = await find_profile_by_user_and_hospital(engine, hospital_id, user_id)
            if not profile:
                profile = await find_profile_by_user_id(engine, user_id)
            if profile:
                authorized_ids.add(str(profile.id))

    elif role == UserRole.HOSPITAL_OWNER.value:
        # Authorized set is ALL doctors belonging to the owner's hospital_id
        if hospital_id:
            profiles = await find_profiles_by_hospital(engine, hospital_id)
            for p in profiles:
                authorized_ids.add(str(p.id))
                if p.user_id:
                    authorized_ids.add(p.user_id)

    logger.debug("Authorized doctor IDs computed for %s (%s): %s", user_id, role, authorized_ids)
    return authorized_ids


async def execute_tool_call(
    engine: AIOEngine,
    current_user: dict,
    tool_name: str,
    tool_args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Security Gate: Intercepts Gemini tool calls and verifies authorization
    BEFORE executing any database query.
    """
    hospital_id = current_user.get("hospital_id")
    user_role = current_user.get("role")
    authorized_doctor_ids = await get_authorized_doctor_ids(engine, current_user)

    logger.info("Intercepted tool call '%s' with args %s for user role '%s'", tool_name, tool_args, user_role)

    if tool_name == "get_appointments":
        requested_doctor_id = tool_args.get("doctor_id")
        start_date = tool_args.get("start_date")
        end_date = tool_args.get("end_date")

        if not requested_doctor_id:
            return {"error": "Missing required argument 'doctor_id'."}

        if not start_date or not end_date:
            return {"error": "Missing required date arguments ('start_date', 'end_date')."}

        # ── CRITICAL SECURITY CHECK ──
        if requested_doctor_id not in authorized_doctor_ids:
            logger.warning(
                "SECURITY REJECTION: User '%s' (role: %s) requested unauthorized doctor_id '%s'. Authorized set: %s",
                current_user.get("email"),
                user_role,
                requested_doctor_id,
                authorized_doctor_ids,
            )
            return {
                "error": (
                    f"Access Denied: You are not authorized to view schedule for doctor_id '{requested_doctor_id}'. "
                    f"Forbidden cross-doctor/cross-tenant request."
                ),
                "status": "UNAUTHORIZED",
            }

        # Authorized! Query appointments matching hospital_id, doctor_id (or matched IDs), and date range
        # Note: appointments in DB may match requested_doctor_id, or mapped profile/user_id
        matched_ids = [requested_doctor_id]
        for aid in authorized_doctor_ids:
            if aid not in matched_ids:
                matched_ids.append(aid)

        appointments = await engine.find(
            AppointmentModel,
            (AppointmentModel.hospital_id == hospital_id)
            & (AppointmentModel.doctor_id.in_(matched_ids))
            & (AppointmentModel.date >= start_date)
            & (AppointmentModel.date <= end_date),
            sort=AppointmentModel.date,
        )

        return {
            "doctor_id": requested_doctor_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_appointments": len(appointments),
            "appointments": [
                {
                    "appointment_id": str(a.id),
                    "patient_name": a.patient_name,
                    "date": a.date,
                    "slot": a.slot,
                    "reason": a.reason,
                    "temperature": a.temperature,
                    "symptoms": [s.value for s in a.symptoms],
                    "is_cancelled": a.is_cancelled,
                    "cancellation_reason": a.cancellation_reason,
                }
                for a in appointments
            ],
        }

    elif tool_name == "get_doctor_list":
        req_hospital_id = tool_args.get("hospital_id") or hospital_id
        # Scoping check: users can only fetch doctors for their own hospital
        if req_hospital_id != hospital_id:
            logger.warning(
                "SECURITY REJECTION: User '%s' requested doctors for hospital_id '%s', but user's hospital is '%s'",
                current_user.get("email"),
                req_hospital_id,
                hospital_id,
            )
            return {
                "error": f"Access Denied: You can only query doctor list for your hospital_id '{hospital_id}'.",
                "status": "UNAUTHORIZED",
            }

        profiles = await find_profiles_by_hospital(engine, hospital_id)
        doctor_list = []
        for p in profiles:
            user = None
            if p.user_id:
                try:
                    user = await engine.find_one(UserModel, UserModel.id == ObjectId(p.user_id))
                except Exception:
                    pass
            doctor_list.append({
                "doctor_id": str(p.id),
                "user_id": p.user_id,
                "name": user.name if user else "Doctor",
                "email": user.email if user else "",
                "specialization": p.specialization,
                "is_active": p.is_active,
            })

        return {"hospital_id": hospital_id, "total_doctors": len(doctor_list), "doctors": doctor_list}

    else:
        return {"error": f"Unknown tool: '{tool_name}'"}
