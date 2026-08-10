import pytest
from datetime import date, timedelta

@pytest.mark.asyncio
async def test_get_doctor_info(async_client):
    """Test retrieving public doctor profile information."""
    response = await async_client.get("/api/v1/doctor-info")
    assert response.status_code == 200
    data = response.json()
    assert data["doctor_name"] == "Dr. Meera Kulkarni"
    assert data["specialization"] == "General Physician"
    assert data["consultation_fee"] == "Rs. 300"
    assert "morning_hours" in data
    assert "evening_hours" in data

@pytest.mark.asyncio
async def test_get_free_slots_today(async_client):
    """Test retrieving available slots for today."""
    today_str = date.today().isoformat()
    response = await async_client.get(f"/api/v1/free-slots?date={today_str}")
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == today_str
    assert isinstance(data["available_slots"], list)
    assert len(data["available_slots"]) == 12
    assert "10:00" in data["available_slots"]

@pytest.mark.asyncio
async def test_get_free_slots_past_date(async_client):
    """Test querying slots for a past date fails with 400 Bad Request."""
    past_date = (date.today() - timedelta(days=1)).isoformat()
    response = await async_client.get(f"/api/v1/free-slots?date={past_date}")
    assert response.status_code == 400
    data = response.json()
    assert "past date" in data["detail"].lower()

@pytest.mark.asyncio
async def test_get_free_slots_out_of_bounds_future_date(async_client):
    """Test querying slots beyond 7 days fails with 400 Bad Request."""
    far_future_date = (date.today() + timedelta(days=10)).isoformat()
    response = await async_client.get(f"/api/v1/free-slots?date={far_future_date}")
    assert response.status_code == 400
    data = response.json()
    assert "7 days" in data["detail"].lower() or "in advance" in data["detail"].lower()

@pytest.mark.asyncio
async def test_doctor_schedule_unauthorized_patient(async_client):
    """Test that a patient token cannot access doctor schedule endpoint."""
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Patient One", "email": "patient1@example.com", "password": "Password123!"},
    )
    login_res = await async_client.post(
        "/api/v1/login",
        json={"email": "patient1@example.com", "password": "Password123!"},
    )
    patient_token = login_res.json()["access_token"]
    
    today_str = date.today().isoformat()
    response = await async_client.get(
        f"/api/v1/doctor/schedule?date={today_str}",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response.status_code == 403
    data = response.json()
    assert "restricted" in data["detail"].lower() or "doctor" in data["detail"].lower()

@pytest.mark.asyncio
async def test_doctor_schedule_authorized(async_client):
    """Test that doctor can fetch schedule."""
    await async_client.post(
        "/api/v1/signup",
        json={"name": "Dr. Test", "email": "dr.meera@citycare.com", "password": "doctor123"},
    )
    login_res = await async_client.post(
        "/api/v1/login",
        json={"email": "dr.meera@citycare.com", "password": "doctor123"},
    )
    assert login_res.status_code == 200
    doctor_token = login_res.json()["access_token"]
    
    today_str = date.today().isoformat()
    response = await async_client.get(
        f"/api/v1/doctor/schedule?date={today_str}",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == today_str
    assert "schedule" in data


@pytest.mark.asyncio
async def test_doctor_stats_authorized(async_client):
    """Test doctor stats endpoint for authorized doctor."""
    login_res = await async_client.post(
        "/api/v1/login",
        json={"email": "dr.meera@citycare.com", "password": "doctor123"},
    )
    assert login_res.status_code == 200
    doctor_token = login_res.json()["access_token"]
    
    response = await async_client.get(
        "/api/v1/doctor/stats",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_registered_patients" in data
    assert "todays_visit_count" in data
    assert "upcoming_visit_count" in data


@pytest.mark.asyncio
async def test_doctor_toggle_unavailability(async_client):
    """Test marking a date as unavailable and verifying status."""
    login_res = await async_client.post(
        "/api/v1/login",
        json={"email": "dr.meera@citycare.com", "password": "doctor123"},
    )
    assert login_res.status_code == 200
    doctor_token = login_res.json()["access_token"]

    target_date = (date.today() + timedelta(days=3)).isoformat()

    # Toggle unavailable = True
    response = await async_client.post(
        "/api/v1/doctor/unavailability",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"date": target_date, "is_unavailable": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_unavailable"] is True
    assert target_date in data["unavailable_dates"]

    # Check unavailability list
    list_res = await async_client.get(
        "/api/v1/doctor/unavailability",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert list_res.status_code == 200
    assert target_date in list_res.json()["unavailable_dates"]

    # Toggle back to available
    toggle_back = await async_client.post(
        "/api/v1/doctor/unavailability",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"date": target_date, "is_unavailable": False},
    )
    assert toggle_back.status_code == 200
    assert target_date not in toggle_back.json()["unavailable_dates"]

