"""
─────────────────────────────────────────────────────────────────────────────
File        : tests/test_admin.py
Purpose     : Integration tests for super-admin hospital management endpoints.

Test Coverage:
    1. SUPER_ADMIN can create a hospital                (happy path)
    2. SUPER_ADMIN can create a hospital owner          (happy path)
    3. Non-super-admin (doctor) receives 403            (auth guard)
    4. Suspended hospital's owner cannot create doctors (Phase 3 — passes now)

Notes:
    - conftest.py seeds a doctor and a patient; it does NOT seed a SUPER_ADMIN.
    - Each test that needs a SUPER_ADMIN provisions one directly via the engine
      fixture from conftest.py, keeping it isolated and not polluting the seed.
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
    """
    Provision a SUPER_ADMIN user directly in the DB and return a valid JWT.

    Using the engine from setup_db ensures this user is cleaned up between
    tests just like all other documents.
    """
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
async def doctor_token(async_client):
    """Return a JWT for the seeded doctor account (role=doctor, not super_admin)."""
    response = await async_client.post(
        "/api/v1/login",
        json={"email": "dr.meera@citycare.com", "password": "doctor123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


# ─── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_super_admin_can_create_hospital(async_client, super_admin_token):
    """
    SUPER_ADMIN can register a new hospital tenant.

    Verifies:
    - 201 Created response.
    - Response contains expected hospital fields.
    - New hospital starts as is_approved=False (not live by default).
    - Response message acknowledges the unapproved state.
    """
    response = await async_client.post(
        "/api/v1/admin/hospitals",
        json={
            "name": "HealthFirst Clinic",
            "address": "45, FC Road, Shivajinagar",
            "city": "Pune",
            "contact_number": "+91-20-9876-5432",
        },
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )

    assert response.status_code == 201, f"Expected 201, got: {response.text}"
    data = response.json()

    assert data["name"] == "HealthFirst Clinic"
    assert data["city"] == "Pune"
    assert data["is_approved"] is False, "Hospital must start unapproved"
    assert data["is_active"] is True
    assert data["owner_id"] == "", "No owner yet — should be empty string"
    assert "hospital_id" in data
    assert len(data["hospital_id"]) == 24, "hospital_id should be a 24-char ObjectId hex"
    assert "message" in data


@pytest.mark.asyncio
async def test_super_admin_can_create_hospital_owner(async_client, super_admin_token):
    """
    SUPER_ADMIN can create a HOSPITAL_OWNER and bind it to the hospital.

    Verifies:
    - Hospital owner is created with 201 Created.
    - Owner receives role=hospital_owner.
    - Response confirms the hospital binding (hospital_id matches).
    - Owner can subsequently log in with their credentials.
    """
    # Step 1: Create the hospital
    hosp_resp = await async_client.post(
        "/api/v1/admin/hospitals",
        json={
            "name": "Sunrise Medical Centre",
            "address": "10, Baner Road",
            "city": "Pune",
            "contact_number": "+91-20-1111-2222",
        },
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert hosp_resp.status_code == 201, f"Hospital creation failed: {hosp_resp.text}"
    hospital_id = hosp_resp.json()["hospital_id"]

    # Step 2: Create the owner bound to this hospital
    owner_resp = await async_client.post(
        f"/api/v1/admin/hospitals/{hospital_id}/owner",
        json={
            "name": "Priya Nair",
            "email": "priya.nair@sunrise.com",
            "password": "OwnerPass@9876",
        },
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert owner_resp.status_code == 201, f"Owner creation failed: {owner_resp.text}"
    owner_data = owner_resp.json()

    assert owner_data["role"] == "hospital_owner"
    assert owner_data["hospital_id"] == hospital_id
    assert owner_data["email"] == "priya.nair@sunrise.com"
    assert "user_id" in owner_data

    # Step 3: Verify the owner can log in
    login_resp = await async_client.post(
        "/api/v1/login",
        json={"email": "priya.nair@sunrise.com", "password": "OwnerPass@9876"},
    )
    assert login_resp.status_code == 200, f"Owner login failed: {login_resp.text}"
    login_data = login_resp.json()
    assert login_data["role"] == "hospital_owner"


@pytest.mark.asyncio
async def test_non_super_admin_gets_403_on_admin_endpoints(
    async_client, doctor_token
):
    """
    A DOCTOR token (or any non-SUPER_ADMIN token) must be rejected with 403
    on all admin endpoints.

    Verifies:
    - POST /v1/admin/hospitals → 403 for a doctor.
    - GET  /v1/admin/hospitals → 403 for a doctor.
    - The detail message references super admin role.
    """
    # Attempt to create a hospital as doctor
    create_resp = await async_client.post(
        "/api/v1/admin/hospitals",
        json={
            "name": "Unauthorized Clinic",
            "address": "Nowhere",
            "city": "Mumbai",
            "contact_number": "+91-00-0000-0000",
        },
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert create_resp.status_code == 403, (
        f"Expected 403 for doctor on POST /admin/hospitals, got {create_resp.status_code}"
    )
    assert "super admin" in create_resp.json()["detail"].lower()

    # Attempt to list hospitals as doctor
    list_resp = await async_client.get(
        "/api/v1/admin/hospitals",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert list_resp.status_code == 403, (
        f"Expected 403 for doctor on GET /admin/hospitals, got {list_resp.status_code}"
    )


@pytest.mark.asyncio
async def test_suspended_hospital_owner_cannot_create_doctors(
    async_client, super_admin_token
):
    """
    An owner of a SUSPENDED hospital must receive 403 when attempting to
    add a doctor to that hospital via POST /api/v1/hospital/doctors.

    Phase 3 enforcement: HospitalController.create_doctor() checks
    hospital.is_active before persisting and raises 403 if False.
    The endpoint used is the owner's own scoped route, not the admin path.
    """
    # Create hospital
    hosp_resp = await async_client.post(
        "/api/v1/admin/hospitals",
        json={
            "name": "Suspended Hospital",
            "address": "1 Closed Lane",
            "city": "Nagpur",
            "contact_number": "+91-07-1234-0000",
        },
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert hosp_resp.status_code == 201
    hospital_id = hosp_resp.json()["hospital_id"]

    # Create owner for the hospital
    owner_resp = await async_client.post(
        f"/api/v1/admin/hospitals/{hospital_id}/owner",
        json={
            "name": "Suspended Owner",
            "email": "suspended.owner@test.com",
            "password": "SuspOwner@1234",
        },
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert owner_resp.status_code == 201

    # Suspend the hospital
    patch_resp = await async_client.patch(
        f"/api/v1/admin/hospitals/{hospital_id}/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_active"] is False

    # Log in as the owner — login itself succeeds (suspension ≠ account ban)
    login_resp = await async_client.post(
        "/api/v1/login",
        json={"email": "suspended.owner@test.com", "password": "SuspOwner@1234"},
    )
    assert login_resp.status_code == 200
    owner_token = login_resp.json()["access_token"]

    # Owner attempts to create a doctor via the Phase 3 scoped endpoint.
    # The HospitalController checks hospital.is_active from the DB and
    # raises 403 because is_active=False.
    add_doctor_resp = await async_client.post(
        "/api/v1/hospital/doctors",
        json={
            "name": "Dr. Test",
            "email": "dr.test@suspended.com",
            "password": "DocPass@1234",
            "specialization": "General Physician",
            "consultation_fee": "Rs. 200",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert add_doctor_resp.status_code == 403, (
        f"Expected 403 for suspended hospital, got {add_doctor_resp.status_code}: "
        f"{add_doctor_resp.text}"
    )
    assert "suspended" in add_doctor_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_platform_stats(async_client, super_admin_token):
    """SUPER_ADMIN can retrieve platform-wide stats."""
    response = await async_client.get(
        "/api/v1/admin/stats",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_hospitals" in data
    assert "active_hospitals" in data
    assert "total_doctors" in data
    assert "total_patients" in data
    assert "total_appointments" in data


@pytest.mark.asyncio
async def test_get_hospital_stats_admin(async_client, super_admin_token):
    """SUPER_ADMIN can retrieve stats for any specific hospital."""
    hosp_resp = await async_client.post(
        "/api/v1/admin/hospitals",
        json={
            "name": "Stats Test Hospital",
            "address": "Stats Lane",
            "city": "Pune",
            "contact_number": "+91-20-8888-9999",
        },
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    hospital_id = hosp_resp.json()["hospital_id"]

    stats_resp = await async_client.get(
        f"/api/v1/admin/hospitals/{hospital_id}/stats",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert stats_resp.status_code == 200
    data = stats_resp.json()
    assert data["hospital_id"] == hospital_id
    assert data["hospital_name"] == "Stats Test Hospital"
    assert "total_doctors" in data
    assert "todays_appointments" in data

