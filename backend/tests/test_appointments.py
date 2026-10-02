import pytest
from datetime import date, timedelta


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _booking_payload(booking_context: dict, **overrides) -> dict:
    """
    Build a minimal valid booking JSON body using the shared booking_context fixture.

    The booking_context provides hospital_id and doctor_id — the two fields
    added in Phase 4. All other fields are set to safe defaults that pass
    Gate 2 validation. Override any field via keyword args.
    """
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    base = {
        "hospital_id": booking_context["hospital_id"],
        "doctor_id": booking_context["doctor_id"],
        "date": tomorrow,
        "slot": "10:00",
        "reason": "Default test reason for appointment",
        "temperature": 98.6,
        "symptoms": ["fever"],
    }
    base.update(overrides)
    return base


# ─── Gate Tests (no auth needed beyond a patient token) ───────────────────────


@pytest.mark.asyncio
async def test_book_appointment_success(async_client, booking_context):
    """Test successful appointment booking with valid parameters."""
    # Signup patient
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Test Patient", "email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    # Login as patient
    login_res = await async_client.post(
        "/api/v1/login",
        json={"email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]

    target_date = (date.today() + timedelta(days=1)).isoformat()

    # Get free slots for the specific doctor at this hospital
    slots_res = await async_client.get(
        f"/api/v1/hospitals/{booking_context['hospital_id']}/doctors/"
        f"{booking_context['doctor_id']}/free-slots?date={target_date}"
    )
    assert slots_res.status_code == 200, f"Free slots failed: {slots_res.text}"
    available_slots = slots_res.json()["available_slots"]
    assert len(available_slots) > 0
    slot_to_book = available_slots[0]

    # Book appointment
    book_res = await async_client.post(
        "/api/v1/book",
        headers={"Authorization": f"Bearer {token}"},
        json=_booking_payload(booking_context, date=target_date, slot=slot_to_book,
                              reason="Routine Checkup for fever and cough",
                              symptoms=["fever", "cough"]),
    )
    assert book_res.status_code == 201
    data = book_res.json()
    assert "appointment_id" in data
    assert data["date"] == target_date
    assert data["slot"] == slot_to_book
    assert data["patient_name"] == "Test Patient"


@pytest.mark.asyncio
async def test_gate1_book_appointment_past_date(async_client, booking_context):
    """Gate 1 Validation: Cannot book for past dates."""
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Test Patient", "email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    login_res = await async_client.post(
        "/api/v1/login",
        json={"email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]

    past_date = (date.today() - timedelta(days=1)).isoformat()
    book_res = await async_client.post(
        "/api/v1/book",
        headers={"Authorization": f"Bearer {token}"},
        json=_booking_payload(booking_context, date=past_date, slot="10:00",
                              reason="Past date check booking reason",
                              symptoms=["cold"]),
    )
    assert book_res.status_code == 400
    assert "past date" in book_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_gate2_book_appointment_invalid_slot(async_client, booking_context):
    """Gate 2 Validation: Cannot book invalid slot string outside clinic slots."""
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Test Patient", "email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    login_res = await async_client.post(
        "/api/v1/login",
        json={"email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]

    target_date = (date.today() + timedelta(days=2)).isoformat()
    book_res = await async_client.post(
        "/api/v1/book",
        headers={"Authorization": f"Bearer {token}"},
        json=_booking_payload(booking_context, date=target_date,
                              slot="03:00",   # Invalid — not in clinic hours
                              reason="Invalid slot time check reason",
                              symptoms=["fever"]),
    )
    assert book_res.status_code == 400
    assert "invalid appointment slot" in book_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_gate3_book_duplicate_same_day(async_client, booking_context):
    """Gate 3 Validation: Patient cannot book multiple appointments on the same day."""
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Test Patient", "email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    login_res = await async_client.post(
        "/api/v1/login",
        json={"email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]

    target_date = (date.today() + timedelta(days=1)).isoformat()

    # Book first slot
    await async_client.post(
        "/api/v1/book",
        headers={"Authorization": f"Bearer {token}"},
        json=_booking_payload(booking_context, date=target_date, slot="10:00",
                              reason="First appointment booking reason",
                              symptoms=["fever"]),
    )

    # Try booking second slot on same date at the same hospital
    book_res = await async_client.post(
        "/api/v1/book",
        headers={"Authorization": f"Bearer {token}"},
        json=_booking_payload(booking_context, date=target_date, slot="11:00",
                              reason="Second appointment booking reason",
                              symptoms=["headache"]),
    )
    assert book_res.status_code == 409
    assert "one appointment per day" in book_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_gate3_cross_hospital_same_day_blocked(async_client, booking_context):
    """Gate 3 Validation: Patient cannot book multiple appointments on the same day across different hospitals."""
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Test Patient 2", "email": "testpatient2@example.com", "password": "SecurePassword123!"},
    )
    login_res = await async_client.post(
        "/api/v1/login",
        json={"email": "testpatient2@example.com", "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]

    target_date = (date.today() + timedelta(days=1)).isoformat()

    # Book first slot
    await async_client.post(
        "/api/v1/book",
        headers={"Authorization": f"Bearer {token}"},
        json=_booking_payload(booking_context, date=target_date, slot="10:00",
                              reason="First appointment booking reason",
                              symptoms=["fever"]),
    )

    # Try booking second slot on same date at another hospital ID
    book_res = await async_client.post(
        "/api/v1/book",
        headers={"Authorization": f"Bearer {token}"},
        json=_booking_payload(booking_context, hospital_id="60d5ecb8b5c9c80015f8e999", date=target_date, slot="12:00",
                              reason="Cross hospital booking attempt",
                              symptoms=["headache"]),
    )
    assert book_res.status_code == 409
    assert "one appointment per day" in book_res.json()["detail"].lower()



@pytest.mark.asyncio
async def test_my_appointments_list(async_client, booking_context):
    """Test fetching patient's booked appointments."""
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Test Patient", "email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    login_res = await async_client.post(
        "/api/v1/login",
        json={"email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]

    target_date = (date.today() + timedelta(days=1)).isoformat()
    await async_client.post(
        "/api/v1/book",
        headers={"Authorization": f"Bearer {token}"},
        json=_booking_payload(booking_context, date=target_date, slot="10:30",
                              reason="Fetching appointment list check",
                              symptoms=["cold"]),
    )

    res = await async_client.get(
        "/api/v1/my-appointments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    appointments = res.json()
    assert isinstance(appointments, list)
    assert len(appointments) >= 1


@pytest.mark.asyncio
async def test_cancel_appointment_and_verify_slot_freed(async_client, booking_context):
    """Test cancelling an appointment as patient and confirming slot becomes available again."""
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Test Patient", "email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    login_res = await async_client.post(
        "/api/v1/login",
        json={"email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]

    target_date = (date.today() + timedelta(days=1)).isoformat()
    book_res = await async_client.post(
        "/api/v1/book",
        headers={"Authorization": f"Bearer {token}"},
        json=_booking_payload(booking_context, date=target_date, slot="12:00",
                              reason="Appointment to be cancelled reason",
                              symptoms=["cough"]),
    )
    assert book_res.status_code == 201, f"Booking failed: {book_res.text}"
    appt_id = book_res.json()["appointment_id"]

    # Cancel appointment
    cancel_res = await async_client.delete(
        f"/api/v1/cancel/{appt_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["appointment_id"] == appt_id

    # Verify free slots now includes the cancelled slot
    slots_res = await async_client.get(
        f"/api/v1/hospitals/{booking_context['hospital_id']}/doctors/"
        f"{booking_context['doctor_id']}/free-slots?date={target_date}"
    )
    assert slots_res.status_code == 200
    free_slots = slots_res.json()["available_slots"]
    assert "12:00" in free_slots


# ─── Existing Gate Tests (no booking_context needed — test auth only) ─────────


@pytest.mark.asyncio
async def test_book_unauthorized(async_client):
    """Test that booking without a token is rejected."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    book_res = await async_client.post(
        "/api/v1/book",
        json={
            "hospital_id": "a" * 24,
            "doctor_id": "b" * 24,
            "date": tomorrow,
            "slot": "10:00",
            "reason": "Unauthorized booking attempt check",
            "temperature": 98.6,
            "symptoms": ["fever"],
        },
    )
    assert book_res.status_code == 401


@pytest.mark.asyncio
async def test_cancel_unauthorized(async_client):
    """Test that cancellation without a token is rejected."""
    cancel_res = await async_client.delete("/api/v1/cancel/000000000000000000000000")
    assert cancel_res.status_code == 401


@pytest.mark.asyncio
async def test_cancel_not_found(async_client):
    """Test that cancelling a non-existent appointment returns 404."""
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Test Patient", "email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    login_res = await async_client.post(
        "/api/v1/login",
        json={"email": "testpatient@example.com", "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]
    cancel_res = await async_client.delete(
        "/api/v1/cancel/000000000000000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cancel_res.status_code == 404


@pytest.mark.asyncio
async def test_gate4_slot_fully_booked(async_client, booking_context):
    """Gate 4 Validation: Cannot book a slot that is already at maximum capacity."""
    # Book the slot with one patient
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Patient One", "email": "patient1@example.com", "password": "SecurePassword123!"},
    )
    login_1 = await async_client.post(
        "/api/v1/login",
        json={"email": "patient1@example.com", "password": "SecurePassword123!"},
    )
    token_1 = login_1.json()["access_token"]

    target_date = (date.today() + timedelta(days=3)).isoformat()

    # First patient books the slot
    res1 = await async_client.post(
        "/api/v1/book",
        headers={"Authorization": f"Bearer {token_1}"},
        json=_booking_payload(booking_context, date=target_date, slot="10:00",
                              reason="First patient booking this slot today",
                              symptoms=["fever"]),
    )
    assert res1.status_code == 201

    # Second patient tries the same slot
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Patient Two", "email": "patient2@example.com", "password": "SecurePassword123!"},
    )
    login_2 = await async_client.post(
        "/api/v1/login",
        json={"email": "patient2@example.com", "password": "SecurePassword123!"},
    )
    token_2 = login_2.json()["access_token"]

    res2 = await async_client.post(
        "/api/v1/book",
        headers={"Authorization": f"Bearer {token_2}"},
        json=_booking_payload(booking_context, date=target_date, slot="10:00",
                              reason="Second patient trying same slot today",
                              symptoms=["cough"]),
    )
    assert res2.status_code == 409
    assert "fully booked" in res2.json()["detail"].lower()
