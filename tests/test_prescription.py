"""
─────────────────────────────────────────────────────────────────────────────
File        : tests/test_prescription.py
Purpose     : Automated pytest suite verifying doctor request acceptance flow,
              prescription creation, PDF generator, patient download flow,
              and RAG pipeline integration.
─────────────────────────────────────────────────────────────────────────────
"""

from datetime import date, timedelta
import pytest

from core.constants import DOCTOR_INFO
from core.models.prescription_model import PrescriptionModel


@pytest.mark.asyncio
async def test_doctor_accept_reject_appointment_flow(async_client, booking_context):
    """Test doctor receiving and accepting an appointment request."""
    # 1. Login as patient & book appointment
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Alice Patient", "email": "alice@example.com", "password": "Password123!"},
    )
    p_login = await async_client.post(
        "/api/v1/login",
        json={"email": "alice@example.com", "password": "Password123!"},
    )
    patient_token = p_login.json()["access_token"]
    p_headers = {"Authorization": f"Bearer {patient_token}"}

    hospital_id = booking_context["hospital_id"]
    doctor_profile_id = booking_context["doctor_id"]

    target_date = (date.today() + timedelta(days=1)).isoformat()

    book_res = await async_client.post(
        "/api/v1/book",
        json={
            "hospital_id": hospital_id,
            "doctor_id": doctor_profile_id,
            "date": target_date,
            "slot": "10:00",
            "reason": "I have persistent high fever and severe headache for two days.",
            "temperature": 100.4,
            "symptoms": ["fever", "headache"],
        },
        headers=p_headers,
    )
    assert book_res.status_code == 201
    appt_id = book_res.json()["appointment_id"]
    assert book_res.json()["status"] == "pending"

    # 2. Login as default doctor (seeded) or doctor from context
    d_login = await async_client.post(
        "/api/v1/login",
        json={"email": "dr.booking@test.com", "password": "Doctor@Test1234"},
    )
    doctor_token = d_login.json()["access_token"]
    d_headers = {"Authorization": f"Bearer {doctor_token}"}

    # 3. Doctor checks schedule
    sched_res = await async_client.get(f"/api/v1/doctor/schedule?date={target_date}", headers=d_headers)
    assert sched_res.status_code == 200
    entries = sched_res.json()["schedule"]
    assert len(entries) >= 1
    target_entry = [e for e in entries if e["appointment_id"] == appt_id][0]
    assert target_entry["status"] == "pending"

    # 4. Doctor accepts appointment
    accept_res = await async_client.patch(f"/api/v1/doctor/appointments/{appt_id}/accept", headers=d_headers)
    assert accept_res.status_code == 200
    assert accept_res.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_create_prescription_and_pdf_generation(async_client, booking_context):
    """Test doctor creating a prescription, PDF generation, and auto status update to completed."""
    # 1. Setup patient & booking
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Bob Patient", "email": "bob@example.com", "password": "Password123!"},
    )
    p_login = await async_client.post(
        "/api/v1/login",
        json={"email": "bob@example.com", "password": "Password123!"},
    )
    patient_token = p_login.json()["access_token"]
    p_headers = {"Authorization": f"Bearer {patient_token}"}

    hospital_id = booking_context["hospital_id"]
    doctor_profile_id = booking_context["doctor_id"]
    target_date = (date.today() + timedelta(days=2)).isoformat()

    book_res = await async_client.post(
        "/api/v1/book",
        json={
            "hospital_id": hospital_id,
            "doctor_id": doctor_profile_id,
            "date": target_date,
            "slot": "11:00",
            "reason": "I have bad cough, congestion, and muscle body ache.",
            "temperature": 99.8,
            "symptoms": ["cough", "bodyache"],
        },
        headers=p_headers,
    )
    appt_id = book_res.json()["appointment_id"]

    # 2. Doctor login & accept
    d_login = await async_client.post(
        "/api/v1/login",
        json={"email": "dr.booking@test.com", "password": "Doctor@Test1234"},
    )
    d_headers = {"Authorization": f"Bearer {d_login.json()['access_token']}"}
    await async_client.patch(f"/api/v1/doctor/appointments/{appt_id}/accept", headers=d_headers)

    # 3. Create prescription
    rx_payload = {
        "appointment_id": appt_id,
        "diagnosis": "Acute Bronchitis with Viral Fever",
        "medications": [
            {
                "medicine_name": "Paracetamol 500mg",
                "dosage": "500 mg",
                "frequency": "1-0-1 after meals",
                "duration": "5 days",
                "instructions": "Take with lukewarm water",
            },
            {
                "medicine_name": "Amoxicillin 250mg",
                "dosage": "250 mg",
                "frequency": "1-1-1",
                "duration": "7 days",
                "instructions": "Complete full antibiotic course",
            },
        ],
        "notes": "Drink warm water, rest well, and avoid cold drinks.",
        "follow_up_date": (date.today() + timedelta(days=9)).isoformat(),
    }

    rx_res = await async_client.post("/api/v1/doctor/prescriptions", json=rx_payload, headers=d_headers)
    assert rx_res.status_code == 201
    rx_data = rx_res.json()

    assert rx_data["appointment_id"] == appt_id
    assert rx_data["diagnosis"] == "Acute Bronchitis with Viral Fever"
    assert len(rx_data["medications"]) == 2
    assert rx_data["pdf_url"] != ""

    # 4. Verify patient can view their prescription list
    p_rx_res = await async_client.get("/api/v1/patient/prescriptions", headers=p_headers)
    assert p_rx_res.status_code == 200
    p_rx_list = p_rx_res.json()
    assert len(p_rx_list) == 1
    assert p_rx_list[0]["prescription_id"] == rx_data["prescription_id"]

    # 5. Verify PDF download endpoint returns PDF file
    pdf_res = await async_client.get(
        f"/api/v1/patient/prescriptions/{rx_data['prescription_id']}/pdf",
        headers=p_headers,
    )
    assert pdf_res.status_code in (200, 307)
    if pdf_res.status_code == 200:
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert len(pdf_res.content) > 100  # PDF content size test


@pytest.mark.asyncio
async def test_prescription_rag_ingestion_and_search(setup_db, monkeypatch):
    """Test the prescription RAG contract without sending medical data to an external embedding API."""
    import chatbot.rag_service as rag_service

    class LocalVectorStore:
        """Small in-memory stand-in that exercises CityCare's RAG integration boundary."""

        def __init__(self):
            self.documents = []

        def add_documents(self, documents):
            self.documents.extend(documents)
            return [str(index) for index, _ in enumerate(documents)]

        def similarity_search_with_score(self, _query, k, filter=None):
            matches = self.documents
            if filter:
                matches = [
                    document
                    for document in matches
                    if all(document.metadata.get(key) == value for key, value in filter.items())
                ]
            return [(document, 0.0) for document in matches[:k]]

    local_vector_store = LocalVectorStore()
    monkeypatch.setattr(rag_service, "get_vector_store", lambda: local_vector_store)

    engine = setup_db
    p_model = PrescriptionModel(
        hospital_id="64b1f2c3d4e5f6a7b8c9d0e1",
        doctor_id="64b1f2c3d4e5f6a7b8c9d0e2",
        doctor_name="Dr. Meera Kulkarni",
        patient_id="patient_test_user_123",
        patient_name="Charlie Test",
        appointment_id="64b1f2c3d4e5f6a7b8c9d0e3",
        date="2026-08-11",
        diagnosis="Migraine with High Fever",
        medications=[
            {
                "medicine_name": "Sumatriptan 50mg",
                "dosage": "50 mg",
                "frequency": "Once as needed",
                "duration": "3 days",
                "instructions": "Take at onset of migraine headache",
            }
        ],
        notes="Avoid bright light and loud noise.",
        follow_up_date="2026-08-18",
        pdf_url="http://example.com/rx.pdf",
    )

    saved = await engine.save(p_model)

    # Ingest into RAG pipeline
    success = rag_service.ingest_prescription_doc(saved)
    assert success is True

    # Search RAG pipeline scoped to patient_id
    search_res = rag_service.search_prescriptions_rag(
        query="migraine headache medicine dosage", patient_id="patient_test_user_123"
    )
    assert search_res["patient_id"] == "patient_test_user_123"
    assert search_res["total_results"] == 1
    assert "Sumatriptan 50mg" in search_res["context"]
