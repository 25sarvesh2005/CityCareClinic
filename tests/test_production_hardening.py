"""
Unit and integration test suite for Production Hardening requirements:
- Centralized configuration loading and APP_ENV validation (development, test, production)
- Rejection of invalid APP_ENV values (prod, staging, empty)
- Rejection of placeholder and weak JWT secrets (<32 chars) in production
- Validation of JWT expiry minutes and algorithm allowlist
- Unsafe demo user seeding prevention and explicit demo password requirements
- Strict CORS origin parsing (schemes, netloc, user credentials, paths, query, fragment, production HTTPS)
- Actual FastAPI CORS middleware preflight OPTIONS header verification
- MongoDB connection error logging safety (no credential/URL leaks) and resource cleanup
- Liveness and readiness health probes
"""

import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.config import (
    get_app_env,
    get_cors_origins,
    get_jwt_expire_minutes,
    get_jwt_secret,
    parse_and_validate_cors_origin,
    should_seed_demo_users,
    validate_app_env,
    validate_config,
)
from core.database.database import connect_to_database
from core.database.seed import seed_initial_users


# ─── APP_ENV Validation Tests ──────────────────────────────────────────────────

@pytest.mark.parametrize("valid_env", ["development", "test", "production", "  DEVELOPMENT  ", "TEST"])
def test_app_env_valid_values(valid_env):
    """Valid APP_ENV strings pass validation."""
    with patch.dict(os.environ, {"APP_ENV": valid_env}, clear=False):
        normalized = get_app_env()
        validate_app_env(normalized)
        assert normalized in ("development", "test", "production")


@pytest.mark.parametrize("invalid_env", ["prod", "staging", "", "   ", "prod_test", "invalid"])
def test_app_env_rejects_unknown_values(invalid_env):
    """Unknown APP_ENV values (e.g. prod, staging) are rejected with a clear ValueError naming APP_ENV."""
    with patch.dict(os.environ, {"APP_ENV": invalid_env}, clear=False):
        normalized = get_app_env()
        with pytest.raises(ValueError) as exc_info:
            validate_app_env(normalized)
        assert "APP_ENV" in str(exc_info.value)
        assert "Invalid APP_ENV value" in str(exc_info.value)


# ─── JWT Configuration & Placeholder Tests ────────────────────────────────────

def test_production_config_rejects_known_placeholders():
    """Production mode rejects known JWT secret placeholders."""
    placeholders = [
        "your-super-secret-key-change-in-production",
        "your-secure-random-secret-key-at-least-16-characters-long",
        "your-secure-random-secret-key-at-least-32-characters-long",
        "some-custom-key-with-change-in-production-suffix",
    ]
    for ph in placeholders:
        prod_env = {
            "APP_ENV": "production",
            "MONGO_URL": "mongodb://localhost:27017",
            "DB_NAME": "citycare_clinic",
            "JWT_SECRET": ph,
        }
        with patch.dict(os.environ, prod_env, clear=False):
            with pytest.raises(ValueError) as exc_info:
                validate_config()
            assert "JWT_SECRET" in str(exc_info.value)
            assert "placeholder" in str(exc_info.value) or "fallback" in str(exc_info.value)


def test_production_config_rejects_short_jwt_secret():
    """Production mode rejects JWT secret shorter than 32 characters."""
    prod_env = {
        "APP_ENV": "production",
        "MONGO_URL": "mongodb://localhost:27017",
        "DB_NAME": "citycare_clinic",
        "JWT_SECRET": "short-20-character-secret!!",
    }
    with patch.dict(os.environ, prod_env, clear=False):
        with pytest.raises(ValueError) as exc_info:
            validate_config()
        assert "JWT_SECRET" in str(exc_info.value)
        assert "at least 32 characters" in str(exc_info.value)


def test_production_config_accepts_valid_32char_jwt_secret():
    """Production mode accepts valid 32+ character random-looking secret."""
    prod_env = {
        "APP_ENV": "production",
        "MONGO_URL": "mongodb://localhost:27017",
        "DB_NAME": "citycare_clinic",
        "JWT_SECRET": "xK9#mP2$vL5nR8qW1zT4yU7jH0cB3fS6",  # 32 chars
        "CORS_ALLOWED_ORIGINS": "https://clinic.example.com",
        "SEED_DEMO_USERS": "false",
    }
    with patch.dict(os.environ, prod_env, clear=False):
        validate_config()  # Should pass cleanly


def test_jwt_expiry_minutes_validation():
    """Invalid JWT_EXPIRE_MINUTES values are rejected."""
    for invalid_val in ["0", "-10", "abc", "600000"]:
        with patch.dict(os.environ, {"JWT_EXPIRE_MINUTES": invalid_val}, clear=False):
            with pytest.raises(ValueError) as exc_info:
                validate_config()
            assert "JWT_EXPIRE_MINUTES" in str(exc_info.value)


@pytest.mark.parametrize("invalid_val", ["0", "-10", "abc", "600000"])
def test_jwt_expiry_getter_never_silently_falls_back(invalid_val):
    """Direct consumers cannot bypass invalid expiry configuration."""
    with patch.dict(os.environ, {"JWT_EXPIRE_MINUTES": invalid_val}, clear=False):
        with pytest.raises(ValueError, match="JWT_EXPIRE_MINUTES"):
            get_jwt_expire_minutes()


def test_jwt_algorithm_validation():
    """Disallowed JWT_ALGORITHM values are rejected."""
    with patch.dict(os.environ, {"JWT_ALGORITHM": "none"}, clear=False):
        with pytest.raises(ValueError) as exc_info:
            validate_config()
        assert "JWT_ALGORITHM" in str(exc_info.value)


# ─── Demo User Seeding Safety Tests ───────────────────────────────────────────

def test_demo_seeding_disabled_by_default():
    """Demo user seeding is disabled by default."""
    with patch.dict(os.environ, {"SEED_DEMO_USERS": "false", "APP_ENV": "development"}, clear=False):
        assert should_seed_demo_users() is False


def test_demo_seeding_forbidden_in_production():
    """Demo user seeding is forbidden in production even if SEED_DEMO_USERS=true."""
    with patch.dict(os.environ, {"SEED_DEMO_USERS": "true", "APP_ENV": "production"}, clear=False):
        assert should_seed_demo_users() is False


@pytest.mark.asyncio
async def test_demo_seeding_fails_without_credentials():
    """Explicit SEED_DEMO_USERS=true fails before partial seeding if password env vars are missing."""
    env_override = {
        "SEED_DEMO_USERS": "true",
        "APP_ENV": "development",
        "DEMO_DOCTOR_PASSWORD": "",
        "DEMO_PATIENT_PASSWORD": "",
        "DEMO_ADMIN_PASSWORD": "",
    }
    with patch.dict(os.environ, env_override, clear=False):
        with patch("core.database.seed.find_user_by_email") as mock_find:
            with pytest.raises(ValueError) as exc_info:
                await seed_initial_users()
            assert "DEMO_DOCTOR_PASSWORD" in str(exc_info.value)
            mock_find.assert_not_called()  # No database queries or partial seeding executed


@pytest.mark.asyncio
async def test_seed_initial_users_skips_when_disabled():
    """seed_initial_users does nothing when should_seed_demo_users is False."""
    with patch("core.database.seed.should_seed_demo_users", return_value=False):
        with patch("core.database.seed.find_user_by_email") as mock_find:
            await seed_initial_users()
            mock_find.assert_not_called()


# ─── CORS Parsing & Middleware Tests ──────────────────────────────────────────

def test_cors_origin_parser_valid_origins():
    """Valid CORS origins parse and normalize cleanly."""
    assert parse_and_validate_cors_origin("http://localhost:5173", is_prod=False) == "http://localhost:5173"
    assert parse_and_validate_cors_origin("https://app.example.com/", is_prod=True) == "https://app.example.com"
    assert parse_and_validate_cors_origin("https://sub.domain.com:8443", is_prod=True) == "https://sub.domain.com:8443"


def test_cors_origin_parser_invalid_origins():
    """Invalid CORS origin formats are rejected."""
    invalid_cases = [
        "*",                              # Incompatible with credentialed CORS
        "https://",                       # Missing netloc
        "https://example.com/path",       # Path not allowed
        "https://user:pass@example.com",  # User credentials not allowed
        "https://example.com?query=1",    # Query string not allowed
        "https://example.com#fragment",   # Fragment not allowed
        "https://example.com:invalid",     # Invalid port
        "https://exa mple.com",            # Whitespace is invalid
        "ftp://example.com",              # Disallowed scheme
    ]
    for origin in invalid_cases:
        with pytest.raises(ValueError):
            parse_and_validate_cors_origin(origin, is_prod=False)


def test_cors_origin_parser_production_https_requirement():
    """Production mode rejects non-HTTPS CORS origins."""
    with pytest.raises(ValueError) as exc_info:
        parse_and_validate_cors_origin("http://app.example.com", is_prod=True)
    assert "HTTPS" in str(exc_info.value)


@pytest.mark.parametrize(
    "webhook_url",
    [
        "https://",
        "http://api.example.com/api/v1/telegram/webhook",
        "https://user@example.com/api/v1/telegram/webhook",
        "https://api.example.com:invalid/api/v1/telegram/webhook",
        "https://api.example.com/wrong/path",
        "https://api.example.com/api/v1/telegram/webhook?token=secret",
    ],
)
def test_production_rejects_invalid_telegram_webhook_urls(webhook_url):
    prod_env = {
        "APP_ENV": "production",
        "MONGO_URL": "mongodb://localhost:27017",
        "DB_NAME": "citycare_clinic",
        "JWT_SECRET": "xK9#mP2$vL5nR8qW1zT4yU7jH0cB3fS6",
        "CORS_ALLOWED_ORIGINS": "https://clinic.example.com",
        "SEED_DEMO_USERS": "false",
        "TELEGRAM_PUBLIC_WEBHOOK_URL": webhook_url,
        "TELEGRAM_WEBHOOK_SECRET": "valid_webhook_secret",
    }
    with patch.dict(os.environ, prod_env, clear=True):
        with pytest.raises(ValueError, match="TELEGRAM_PUBLIC_WEBHOOK_URL"):
            validate_config()


@pytest.mark.parametrize("webhook_secret", ["contains spaces", "invalid/slash", "x" * 257])
def test_production_rejects_invalid_telegram_webhook_secrets(webhook_secret):
    prod_env = {
        "APP_ENV": "production",
        "MONGO_URL": "mongodb://localhost:27017",
        "DB_NAME": "citycare_clinic",
        "JWT_SECRET": "xK9#mP2$vL5nR8qW1zT4yU7jH0cB3fS6",
        "CORS_ALLOWED_ORIGINS": "https://clinic.example.com",
        "SEED_DEMO_USERS": "false",
        "TELEGRAM_PUBLIC_WEBHOOK_URL": "https://api.example.com/api/v1/telegram/webhook",
        "TELEGRAM_WEBHOOK_SECRET": webhook_secret,
    }
    with patch.dict(os.environ, prod_env, clear=True):
        with pytest.raises(ValueError, match="TELEGRAM_WEBHOOK_SECRET"):
            validate_config()


@pytest.mark.asyncio
async def test_cors_middleware_options_response(async_client):
    """OPTIONS preflight request returns correct Access-Control-Allow-Origin header."""
    response = await async_client.options(
        "/api/v1/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


# ─── Database Logging Security Tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_database_connection_failure_does_not_log_credentials(caplog):
    """Database connection failure logs class name only and does not leak credentials."""
    secret_sentinel = "sensitive-connection-value-SuperSecretPassword123"

    mock_client_class = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.admin.command = AsyncMock(
        side_effect=Exception(f"Connection failed to {secret_sentinel}")
    )
    mock_client_class.return_value = mock_client_instance

    with patch("core.database.database.AsyncIOMotorClient", mock_client_class):
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception):
                await connect_to_database()

    # Verify secret sentinel and URI never appear in logs
    captured_text = caplog.text
    assert secret_sentinel not in captured_text
    assert "SuperSecretPassword123" not in captured_text


# ─── Health Probes Tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_liveness_probe_without_db(async_client):
    """GET /health/liveness returns HTTP 200 without DB dependency."""
    response = await async_client.get("/health/liveness")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_readiness_probe_healthy(async_client, setup_db):
    """GET /health/readiness returns HTTP 200 when database is connected."""
    response = await async_client.get("/health/readiness")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}


@pytest.mark.asyncio
async def test_readiness_probe_unhealthy(async_client):
    """GET /health/readiness returns HTTP 503 when database engine is unavailable."""
    with patch("main.get_engine", side_effect=RuntimeError("Engine not initialized")):
        response = await async_client.get("/health/readiness")
        assert response.status_code == 503
        assert response.json()["detail"] == {"status": "not_ready", "database": "disconnected"}
