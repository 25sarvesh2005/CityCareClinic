"""Authorized MCP wrappers around the established prescription RAG service."""

from __future__ import annotations

from typing import Any

from chatbot.rag_service import search_prescriptions_rag
from core.database.database import get_engine
from mcp_server.tools.auth import RequesterContext, authorize_patient_access


ALL_PRESCRIPTIONS_QUERY = "all documented prescription details, medicines, dosage, instructions, notes and follow-up"


async def get_prescription_for_requester(
    patient_id: str, requester: RequesterContext, engine=None
) -> dict[str, Any]:
    """Retrieve patient-scoped prescription evidence after authorization succeeds."""
    active_engine = engine or get_engine()
    await authorize_patient_access(active_engine, requester, patient_id)
    return search_prescriptions_rag(query=ALL_PRESCRIPTIONS_QUERY, patient_id=patient_id)


async def search_prescriptions_for_requester(
    patient_id: str, query: str, requester: RequesterContext, engine=None
) -> dict[str, Any]:
    """Search a patient's records only after independently checking access."""
    if not query.strip():
        raise ValueError("A non-empty prescription search query is required.")
    active_engine = engine or get_engine()
    await authorize_patient_access(active_engine, requester, patient_id)
    return search_prescriptions_rag(query=query, patient_id=patient_id)
