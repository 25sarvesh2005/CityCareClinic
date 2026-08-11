import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Set test env variables before importing app
os.environ["DB_NAME"] = "citycare_clinic_test_db"
os.environ["JWT_SECRET"] = "test-secret-key-for-unit-testing"
os.environ["DOCTOR_EMAIL"] = "dr.meera@citycare.com"

from main import app
from core.database.database import connect_to_database, close_database_connection, get_engine
from core.database.seed import seed_initial_users
from core.models.user_model import UserModel
from core.models.appointment_model import AppointmentModel
from core.models.hospital_model import HospitalModel
from core.models.doctor_profile_model import DoctorProfileModel
from core.models.prescription_model import PrescriptionModel


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """
    Initialize test database connection per test function.

    Cleans all collections (users, appointments, hospitals, doctor_profiles, prescriptions)
    before and after each test so tests are fully isolated. Seeds the default
    doctor and patient accounts after cleanup.
    """
    await connect_to_database()
    engine = get_engine()

    # Clean all collections before each test run
    for model in (UserModel, AppointmentModel, HospitalModel, DoctorProfileModel, PrescriptionModel):
        try:
            await engine.remove(model)
        except Exception:
            pass

    # Seed default doctor and patient accounts
    await seed_initial_users()

    yield engine

    # Clean up and close connection after test
    for model in (UserModel, AppointmentModel, HospitalModel, DoctorProfileModel, PrescriptionModel):
        try:
            await engine.remove(model)
        except Exception:
            pass
    await close_database_connection()


@pytest_asyncio.fixture
async def async_client():
    """Async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def booking_context(setup_db, async_client):
    """
    Provision a complete hospital + owner + doctor and return their IDs.

    Used by all booking tests to supply the required hospital_id and
    doctor_id fields in POST /api/v1/book requests. Centralises setup
    here so individual tests don't repeat it.

    Yields:
        dict with keys:
            hospital_id  (str): 24-char ObjectId hex of the test hospital.
            doctor_id    (str): 24-char ObjectId hex of the doctor's profile
                               (use as doctor_id in booking requests).
    """
    from common.auth import hash_password
    from core.constants import UserRole
    from core.models.user_model import UserModel as _UserModel

    import uuid
    uid = uuid.uuid4().hex[:6]
    admin_email = f"admin_{uid}@booking.com"
    owner_email = f"owner_{uid}@test.com"

    engine = setup_db

    # 1. Create a SUPER_ADMIN
    admin = _UserModel(
        name="Test Admin",
        email=admin_email,
        hashed_password=hash_password("Admin@Test123"),
        role=UserRole.SUPER_ADMIN,
        hospital_id=None,
    )
    await engine.save(admin)

    # 2. Log in as admin
    admin_login = await async_client.post(
        "/api/v1/login",
        json={"email": admin_email, "password": "Admin@Test123"},
    )
    assert admin_login.status_code == 200, f"Admin login failed: {admin_login.text}"
    admin_token = admin_login.json()["access_token"]

    # 3. Create a hospital
    hosp_resp = await async_client.post(
        "/api/v1/admin/hospitals",
        json={
            "name": "Test Booking Hospital",
            "address": "1 Test Avenue",
            "city": "Testcity",
            "contact_number": "+91-00-1111-2222",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert hosp_resp.status_code == 201, f"Hospital creation failed: {hosp_resp.text}"
    hospital_id = hosp_resp.json()["hospital_id"]

    # 4. Approve the hospital (so it shows in discovery)
    await async_client.patch(
        f"/api/v1/admin/hospitals/{hospital_id}/status",
        json={"is_approved": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # 5. Create a hospital owner
    owner_resp = await async_client.post(
        f"/api/v1/admin/hospitals/{hospital_id}/owner",
        json={
            "name": "Booking Owner",
            "email": owner_email,
            "password": "Owner@Test1234",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert owner_resp.status_code == 201, f"Owner creation failed: {owner_resp.text}"

    # 6. Log in as owner
    owner_login = await async_client.post(
        "/api/v1/login",
        json={"email": owner_email, "password": "Owner@Test1234"},
    )
    assert owner_login.status_code == 200
    owner_token = owner_login.json()["access_token"]

    # 7. Create a doctor
    doctor_resp = await async_client.post(
        "/api/v1/hospital/doctors",
        json={
            "name": "Dr. Booking Test",
            "email": "dr.booking@test.com",
            "password": "Doctor@Test1234",
            "specialization": "General Physician",
            "consultation_fee": "Rs. 300",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert doctor_resp.status_code == 201, f"Doctor creation failed: {doctor_resp.text}"
    doctor_profile_id = doctor_resp.json()["profile_id"]

    yield {
        "hospital_id": hospital_id,
        "doctor_id": doctor_profile_id,
    }
