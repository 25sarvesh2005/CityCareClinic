import pytest

@pytest.mark.asyncio
async def test_doctor_login_success(async_client):
    """Test login with default seeded doctor credentials."""
    response = await async_client.post(
        "/api/v1/login",
        json={"email": "dr.meera@citycare.com", "password": "doctor123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "doctor"
    assert data["name"] == "Dr. Meera Kulkarni"

@pytest.mark.asyncio
async def test_patient_signup_success(async_client):
    """Test patient registration with valid email and password."""
    response = await async_client.post(
        "/api/v1/signup",
        json={
            "name": "Test Patient",
            "email": "testpatient@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 200 or response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Patient"
    assert data["email"] == "testpatient@example.com"
    assert data["role"] == "patient"
    assert "user_id" in data

@pytest.mark.asyncio
async def test_patient_signup_duplicate_email(async_client):
    """Test that duplicate email registration is rejected with 409 Conflict."""
    # First signup
    await async_client.post(
        "/api/v1/signup",
        json={
            "name": "First Signup Patient",
            "email": "duplicate@example.com",
            "password": "SecurePassword123!",
        },
    )
    # Second signup with same email
    response = await async_client.post(
        "/api/v1/signup",
        json={
            "name": "Duplicate Patient",
            "email": "duplicate@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 409
    data = response.json()
    assert "already exists" in data["detail"].lower()

@pytest.mark.asyncio
async def test_login_invalid_password(async_client):
    """Test login failure with wrong password."""
    response = await async_client.post(
        "/api/v1/login",
        json={"email": "dr.meera@citycare.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert "invalid email address or password" in data["detail"].lower()

@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client):
    """Test login failure with email not registered."""
    response = await async_client.post(
        "/api/v1/login",
        json={"email": "nobody@example.com", "password": "SomePassword123!"},
    )
    assert response.status_code == 401
