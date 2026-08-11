"""
tests/test_rag.py - Automated Tests for RAG Vector Search & Handbook Tool Dispatcher
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from chatbot.rag_service import DEFAULT_PDF_PATH, ingest_pdf, search_handbook
from chatbot.tools import execute_tool_call


def test_pdf_existence():
    """Verify that CityCare Patient Handbook PDF exists at the expected path."""
    assert os.path.exists(DEFAULT_PDF_PATH), f"Handbook PDF missing at {DEFAULT_PDF_PATH}"


@pytest.mark.asyncio
async def test_search_handbook_mocked():
    """Test search_handbook function with mocked Chroma vector store."""
    mock_doc = MagicMock()
    mock_doc.metadata = {"page": 1, "source": "CityCare-Clinic-Patient-Handbook.pdf"}
    mock_doc.page_content = "Patients must cancel appointments at least 24 hours in advance."

    mock_vector_store = MagicMock()
    mock_vector_store.similarity_search_with_score.return_value = [(mock_doc, 0.15)]

    with patch("chatbot.rag_service.get_vector_store", return_value=mock_vector_store):
        result = search_handbook("cancellation policy", top_k=1)

    assert result["total_results"] == 1
    assert "24 hours" in result["context"]
    assert result["snippets"][0]["page"] == 2


@pytest.mark.asyncio
async def test_execute_tool_call_search_patient_handbook():
    """Test execute_tool_call security gate for search_patient_handbook tool."""
    mock_engine = MagicMock()
    mock_user = {
        "user_id": "usr_patient_123",
        "role": "patient",
        "hospital_id": "hosp_123",
        "email": "patient@example.com",
    }

    mock_rag_result = {
        "query": "opening hours",
        "total_results": 1,
        "snippets": [{"page": 1, "source": "Handbook.pdf", "text": "Clinic is open Mon-Fri 8am-6pm."}],
        "context": "Clinic is open Mon-Fri 8am-6pm.",
    }

    with patch("chatbot.tools.get_authorized_doctor_ids", new_callable=AsyncMock) as mock_auth, \
         patch("chatbot.rag_service.search_handbook", return_value=mock_rag_result):
        mock_auth.return_value = set()

        response = await execute_tool_call(
            engine=mock_engine,
            current_user=mock_user,
            tool_name="search_patient_handbook",
            tool_args={"query": "opening hours"},
        )

    assert response["total_results"] == 1
    assert "Mon-Fri 8am-6pm" in response["context"]
