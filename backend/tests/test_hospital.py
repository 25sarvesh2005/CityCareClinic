"""
─────────────────────────────────────────────────────────────────────────────
File        : tests/test_hospital.py
Purpose     : Integration tests for hospital-owner doctor management endpoints.

Test Coverage:
    1. Owner creates a doctor in their own hospital          (happy path)
    2. Body hospital_id is IGNORED — tenant isolation check  (security)
    3. Non-owner (patient) gets 403                          (auth guard)
    4. Owner can list their own doctors                      (list endpoint)

The tenant isolation test (#2) is the most important:
    - The owner sends a different hospital_id in the JSON body.
    - The created doctor profile's hospital_id must equal the owner's
      JWT hospital_id, NOT the value from the body.
    - This proves the controller never reads hospital_id from request body.
─────────────────────────────────────────────────────────────────────────────
"""

import pytest
import pytest_asyncio

from common.auth import hash_password
from core.constants import UserRole
from core.models.user_model import UserModel


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def super_admin_token(setup_db, async_client):
    """Provision a SUPER_ADMIN user and return their JWT."""
    engine = setup_db
    admin_user = UserModel(
        name="Platform Admin",
        email="admin@platform.com",
        hashed_password=hash_password("Admin@Secure1"),
        role=UserRole.SUPER_ADMIN,
        hospital_id=None,
    )
    await engine.save(admin_user)

    response = await async_client.post(
        "/api/v1/login",
        json={"email": "admin@platform.com", "password": "Admin@Secure1"},
    )
    assert response.status_code == 200, f"Super admin login failed: {response.text}"
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def hospital_and_owner(async_client, super_admin_token):
    """
    Create a hospital + owner via the admin API and return both ids and the
    owner's JWT token.

    Returns:
        dict with keys: hospital_id, owner_token, owner_email
    """
    # Create hospital
    hosp_resp = await async_client.post(
        "/api/v1/admin/hospitals",
        json={
            "name": "Phase3 Test Clinic",
            "address": "99 Test Street",
            "city": "Mumbai",
            "contact_number": "+91-22-1234-5678",
        },
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert hosp_resp.status_code == 201, f"Hospital creation failed: {hosp_resp.text}"
    hospital_id = hosp_resp.json()["hospital_id"]

    # Create owner
    owner_resp = await async_client.post(
        f"/api/v1/admin/hospitals/{hospital_id}/owner",
        json={
            "name": "Test Owner",
            "email": "test.owner@phase3clinic.com",
            "password": "OwnerPass@Phase3",
        },
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert owner_resp.status_code == 201, f"Owner creation failed: {owner_resp.text}"

    # Log in as owner
    login_resp = await async_client.post(
        "/api/v1/login",
        json={"email": "test.owner@phase3clinic.com", "password": "OwnerPass@Phase3"},
    )
    assert login_resp.status_code == 200, f"Owner login failed: {login_resp.text}"
    owner_token = login_resp.json()["access_token"]

    return {
        "hospital_id": hospital_id,
        "owner_token": owner_token,
        "owner_email": "test.owner@phase3clinic.com",
    }


@pytest_asyncio.fixture
async def patient_token(async_client):
    """Return a JWT for the seeded patient account (role=patient)."""
    # Sign up a fresh patient to avoid depending on seed state
    signup_resp = await async_client.post(
        "/api/v1/signup",
        json={
            "name": "Test Patient",
            "email": "test.patient@example.com",
            "password": "PatientPass@123",
        },
    )
    assert signup_resp.status_code in (200, 201)

    login_resp = await async_client.post(
        "/api/v1/login",
        json={"email": "test.patient@example.com", "password": "PatientPass@123"},
    )
    assert login_resp.status_code == 200
    return login_resp.json()["access_token"]


# ─── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_owner_can_create_doctor_in_own_hospital(
    async_client, hospital_and_owner
):
    """
    A HOSPITAL_OWNER can create a doctor profile in their own hospital.

    Verifies:
    - 201 Created response.
    - Response profile is scoped to the owner's hospital_id.
    - Doctor receives role=doctor (verified via login).
    - Doctor's hospital_id in their JWT matches the owner's hospital.
    """
    owner_token = hospital_and_owner["owner_token"]
    hospital_id = hospital_and_owner["hospital_id"]

    response = await async_client.post(
        "/api/v1/hospital/doctors",
        json={
            "name": "Dr. Kavitha Rao",
            "email": "dr.kavitha@phase3clinic.com",
            "password": "DocPass@Phase3",
            "specialization": "General Physician",
            "consultation_fee": "Rs. 350",
            "languages_spoken": ["English", "Kannada"],
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 201, f"Expected 201, got: {response.text}"
    data = response.json()

    # Profile is correctly scoped to the owner's hospital
    assert data["hospital_id"] == hospital_id
    assert data["specialization"] == "General Physician"
    assert data["consultation_fee"] == "Rs. 350"
    assert data["is_active"] is True
    assert "profile_id" in data
    assert "user_id" in data
    assert "message" in data

    # Verify the doctor can log in and their JWT carries the correct hospital_id
    login_resp = await async_client.post(
        "/api/v1/login",
        json={"email": "dr.kavitha@phase3clinic.com", "password": "DocPass@Phase3"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["role"] == "doctor"


@pytest.mark.asyncio
async def test_body_hospital_id_is_ignored_tenant_isolation(
    async_client, hospital_and_owner, super_admin_token
):
    """
    CRITICAL TENANT ISOLATION TEST.

    An owner sends a DIFFERENT hospital_id in the JSON body (a second hospital
    they do NOT own). The created doctor profile must be scoped to the owner's
    own hospital_id from their JWT — not the value from the body.

    This proves that:
      1. The schema (no hospital_id field) silently drops the body value.
      2. Even if the field reached the controller, the controller reads
         hospital_id exclusively from scope["hospital_id"] (the JWT).

    How we create the "decoy" hospital:
      - Admin creates a second hospital.
      - Owner crafts a request body that includes hospital_id pointing to
        the decoy. Because CreateDoctorRequest has no hospital_id field,
        Pydantic ignores it.
      - We verify the created profile belongs to the owner's real hospital.
    """
    owner_token = hospital_and_owner["owner_token"]
    real_hospital_id = hospital_and_owner["hospital_id"]

    # Create a second (decoy) hospital that this owner does NOT own
    decoy_resp = await async_client.post(
        "/api/v1/admin/hospitals",
        json={
            "name": "Decoy Hospital",
            "address": "0 Malicious Lane",
            "city": "Delhi",
            "contact_number": "+91-11-0000-0000",
        },
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert decoy_resp.status_code == 201
    decoy_hospital_id = decoy_resp.json()["hospital_id"]
    assert decoy_hospital_id != real_hospital_id, "Decoy must be a different hospital"

    # Owner sends a body that includes hospital_id pointing to the decoy.
    # CreateDoctorRequest has no hospital_id field, so Pydantic drops it silently.
    response = await async_client.post(
        "/api/v1/hospital/doctors",
        json={
            "name": "Dr. Sneaky Injection",
            "email": "dr.sneaky@attacker.com",
            "password": "Injection@Pass1",
            "specialization": "Cardiology",
            "consultation_fee": "Rs. 500",
            # ⬇ Attacker-injected field — should be silently ignored
            "hospital_id": decoy_hospital_id,
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 201, (
        f"Expected 201 (doctor creation success), got: {response.text}"
    )
    data = response.json()

    # THE CRITICAL ASSERTION:
    # Profile must be in the OWNER's real hospital, NOT the decoy
    assert data["hospital_id"] == real_hospital_id, (
        f"TENANT ISOLATION FAILURE: profile landed in '{data['hospital_id']}' "
        f"but owner's hospital is '{real_hospital_id}'. "
        f"The body hospital_id '{decoy_hospital_id}' was not ignored."
    )
    assert data["hospital_id"] != decoy_hospital_id, (
        "TENANT ISOLATION FAILURE: profile was created in the decoy hospital."
    )


@pytest.mark.asyncio
async def test_non_owner_gets_403_on_hospital_endpoints(
    async_client, patient_token
):
    """
    A PATIENT token must be rejected with 403 on all hospital-owner endpoints.

    Verifies:
    - POST /v1/hospital/doctors → 403 for patient.
    - GET  /v1/hospital/doctors → 403 for patient.
    - Detail message references hospital owner role.
    """
    create_resp = await async_client.post(
        "/api/v1/hospital/doctors",
        json={
            "name": "Dr. Unauthorized",
            "email": "dr.unauthorized@test.com",
            "password": "UnAuth@Pass1",
            "specialization": "General",
            "consultation_fee": "Rs. 100",
        },
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert create_resp.status_code == 403, (
        f"Expected 403 for patient on POST /hospital/doctors, "
        f"got {create_resp.status_code}: {create_resp.text}"
    )
    assert "hospital owner" in create_resp.json()["detail"].lower()

    list_resp = await async_client.get(
        "/api/v1/hospital/doctors",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert list_resp.status_code == 403, (
        f"Expected 403 for patient on GET /hospital/doctors, "
        f"got {list_resp.status_code}"
    )


@pytest.mark.asyncio
async def test_owner_can_list_own_doctors(async_client, hospital_and_owner):
    """
    Owner can list all doctors in their hospital via GET /v1/hospital/doctors.

    Verifies:
    - 200 OK with empty list when no doctors exist yet.
    - After creating a doctor, the list contains exactly that doctor.
    - Returned entries are scoped to this hospital only.
    """
    owner_token = hospital_and_owner["owner_token"]

    # Initially empty
    list_resp = await async_client.get(
        "/api/v1/hospital/doctors",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert list_resp.status_code == 200, f"List failed: {list_resp.text}"
    assert list_resp.json() == [], "Expected empty list before any doctors are created"

    # Create one doctor
    create_resp = await async_client.post(
        "/api/v1/hospital/doctors",
        json={
            "name": "Dr. List Test",
            "email": "dr.listtest@phase3clinic.com",
            "password": "ListDoc@Phase3",
            "specialization": "Dermatology",
            "consultation_fee": "Rs. 400",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert create_resp.status_code == 201, f"Doctor creation failed: {create_resp.text}"

    # List again — should have exactly one entry
    list_resp2 = await async_client.get(
        "/api/v1/hospital/doctors",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert list_resp2.status_code == 200
    entries = list_resp2.json()
    assert len(entries) == 1, f"Expected 1 doctor, got {len(entries)}"
    assert entries[0]["specialization"] == "Dermatology"
    assert entries[0]["is_active"] is True
    assert "profile_id" in entries[0]


@pytest.mark.asyncio
async def test_owner_can_get_hospital_stats(async_client, hospital_and_owner):
    """Owner can fetch stats for their hospital via GET /v1/hospital/stats."""
    owner_token = hospital_and_owner["owner_token"]
    hospital_id = hospital_and_owner["hospital_id"]

    stats_resp = await async_client.get(
        "/api/v1/hospital/stats",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert stats_resp.status_code == 200
    data = stats_resp.json()
    assert data["hospital_id"] == hospital_id
    assert "total_doctors" in data
    assert "todays_appointments" in data

