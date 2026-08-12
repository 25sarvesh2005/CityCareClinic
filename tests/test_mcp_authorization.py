from unittest.mock import AsyncMock, MagicMock

import pytest

from core.constants import UserRole
from mcp_server.tools.auth import MCPAuthorizationError, RequesterContext
from mcp_server.tools.prescription_tools import get_prescription_for_requester


@pytest.mark.asyncio
async def test_patient_cross_patient_prescription_is_rejected_before_any_query(monkeypatch):
    engine = AsyncMock()
    search = MagicMock()
    monkeypatch.setattr("mcp_server.tools.prescription_tools.search_prescriptions_rag", search)
    requester = RequesterContext(user_id="patient-a", role=UserRole.PATIENT.value, hospital_id=None)

    with pytest.raises(MCPAuthorizationError, match="only their own records"):
        await get_prescription_for_requester("patient-b", requester, engine=engine)

    engine.find_one.assert_not_called()
    search.assert_not_called()


@pytest.mark.asyncio
async def test_authorized_patient_reaches_only_their_scoped_rag_search(monkeypatch):
    engine = AsyncMock()
    expected = {"patient_id": "patient-a", "snippets": [{"prescription_id": "rx-1"}]}
    search = MagicMock(return_value=expected)
    monkeypatch.setattr("mcp_server.tools.prescription_tools.search_prescriptions_rag", search)
    requester = RequesterContext(user_id="patient-a", role=UserRole.PATIENT.value, hospital_id=None)

    result = await get_prescription_for_requester("patient-a", requester, engine=engine)

    assert result == expected
    search.assert_called_once_with(
        query="all documented prescription details, medicines, dosage, instructions, notes and follow-up",
        patient_id="patient-a",
    )
