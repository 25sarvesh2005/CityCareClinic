"""
Centralized Configuration and Environment Management for CityCare Clinic.

Ensures project-root .env is loaded reliably, reads settings, and provides
production configuration validation without architectural rewrites.
"""

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

# Resolve project root path (directory containing main.py and .env)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

VALID_APP_ENVS = {"development", "test", "production"}
_KNOWN_DEV_FALLBACKS = {
    "your-super-secret-key-change-in-production",
    "your-secure-random-secret-key-at-least-16-characters-long",
    "your-secure-random-secret-key-at-least-32-characters-long",
}
MIN_JWT_SECRET_LENGTH = 32


def load_project_env() -> None:
    """
    Load environment variables from the project root .env file.
    Environment variables supplied by hosting providers take precedence (override=False).
    """
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=False)


# Auto-load on import so modules reading os.getenv get project-root .env values
load_project_env()


def get_app_env() -> str:
    """Return normalized APP_ENV value."""
    raw = os.getenv("APP_ENV")
    if raw is None:
        return "development"
    val = raw.strip().lower()
    if not val:
        return ""
    return val


def validate_app_env(env_val: str) -> None:
    """Validate that APP_ENV is one of the allowed environments."""
    if env_val not in VALID_APP_ENVS:
        raise ValueError(
            f"Invalid APP_ENV value '{env_val}'. Must be one of: 'development', 'test', 'production'."
        )


def is_production() -> bool:
    """Check if running in production environment."""
    return get_app_env() == "production"


def get_mongo_url() -> str:
    """Return the configured MongoDB connection URL."""
    return os.getenv("MONGO_URL", "mongodb://localhost:27017")


def get_db_name() -> str:
    """Return the configured database name."""
    return os.getenv("DB_NAME", "citycare_clinic")


def get_jwt_secret() -> str:
    """Return the configured JWT secret key."""
    return os.getenv("JWT_SECRET", "your-super-secret-key-change-in-production")


def get_jwt_algorithm() -> str:
    """Return the configured JWT signing algorithm."""
    return os.getenv("JWT_ALGORITHM", "HS256").strip().upper()


def get_jwt_expire_minutes() -> int:
    """Return the JWT token expiry in minutes."""
    try:
        expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "JWT_EXPIRE_MINUTES must be a positive integer between 1 and 525600."
        ) from exc
    if not 1 <= expire_minutes <= 525600:
        raise ValueError(
            "JWT_EXPIRE_MINUTES must be a positive integer between 1 and 525600."
        )
    return expire_minutes


def should_seed_demo_users() -> bool:
    """
    Check if demo user seeding is enabled.
    Forbidden in production; disabled by default in development and test.
    """
    if is_production():
        return False
    val = os.getenv("SEED_DEMO_USERS", "false").lower().strip()
    return val in ("true", "1", "yes")


def parse_and_validate_cors_origin(origin: str, is_prod: bool) -> str:
    """
    Validate and normalize a single CORS origin URL using urllib.parse.urlsplit.
    """
    origin = origin.strip()
    if not origin:
        raise ValueError("CORS origin cannot be empty.")
    if any(character.isspace() for character in origin):
        raise ValueError("CORS origin cannot contain whitespace.")

    if origin == "*":
        raise ValueError(
            "Wildcard '*' is forbidden in CORS_ALLOWED_ORIGINS when credentials are enabled."
        )

    parsed = urlsplit(origin)

    if not parsed.scheme or parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid CORS origin scheme in '{origin}'. Must be http or https.")

    if is_prod and parsed.scheme != "https":
        raise ValueError(f"Production configuration error: CORS origin must use HTTPS scheme, got '{origin}'.")

    if not parsed.netloc or not parsed.hostname:
        raise ValueError(f"Invalid CORS origin netloc/hostname in '{origin}'.")

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"Invalid CORS origin port in '{origin}'.") from exc

    if parsed.username or parsed.password:
        raise ValueError(f"CORS origin cannot contain user credentials in '{origin}'.")

    if parsed.path not in ("", "/"):
        raise ValueError(f"CORS origin cannot contain a path in '{origin}'.")

    if parsed.query:
        raise ValueError(f"CORS origin cannot contain query parameters in '{origin}'.")

    if parsed.fragment:
        raise ValueError(f"CORS origin cannot contain a fragment in '{origin}'.")

    hostname = parsed.hostname
    authority = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None:
        authority = f"{authority}:{port}"
    return f"{parsed.scheme}://{authority}"


def get_cors_origins() -> list[str]:
    """
    Parse and validate allowed CORS origins.
    Development defaults to http://localhost:5173 and http://127.0.0.1:5173.
    Production requires explicit HTTPS origins and rejects wildcard '*'.
    """
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    is_prod = is_production()

    if not raw:
        if is_prod:
            raise ValueError(
                "Production configuration error: CORS_ALLOWED_ORIGINS must be explicitly configured."
            )
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    raw_items = [item.strip() for item in raw.split(",") if item.strip()]

    if not raw_items:
        if is_prod:
            raise ValueError(
                "Production configuration error: CORS_ALLOWED_ORIGINS contains no valid origins."
            )
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    validated_origins = []
    seen = set()

    for item in raw_items:
        normalized = parse_and_validate_cors_origin(item, is_prod)
        if normalized not in seen:
            seen.add(normalized)
            validated_origins.append(normalized)

    return validated_origins


def validate_jwt_config(env: str) -> None:
    """Validate JWT configuration settings."""
    # 1. Expiry minutes validation
    get_jwt_expire_minutes()

    # 2. Algorithm validation
    alg = os.getenv("JWT_ALGORITHM", "HS256").strip().upper()
    allowed_algs = {"HS256", "HS384", "HS512"}
    if alg not in allowed_algs:
        raise ValueError(
            f"JWT_ALGORITHM '{alg}' is not allowed. Must be one of: {', '.join(sorted(allowed_algs))}."
        )

    # 3. Production secret validation
    if env == "production":
        secret = os.getenv("JWT_SECRET", "").strip()
        if not secret:
            raise ValueError("Production configuration error: JWT_SECRET must be explicitly configured.")

        lower_secret = secret.lower()
        if (
            secret in _KNOWN_DEV_FALLBACKS
            or "change-in-production" in lower_secret
            or "your-secure-random" in lower_secret
            or "placeholder" in lower_secret
        ):
            raise ValueError(
                "Production configuration error: JWT_SECRET cannot use a known fallback or placeholder value."
            )

        if len(secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                f"Production configuration error: JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters long."
            )


def validate_config() -> None:
    """
    Validate application configuration based on APP_ENV.
    Raises ValueError detailing the misconfigured parameter without exposing secret values.
    """
    env = get_app_env()
    validate_app_env(env)
    validate_jwt_config(env)

    # In production, enforce strict requirements
    if env == "production":
        # 1. MongoDB requirements
        if not os.getenv("MONGO_URL", "").strip():
            raise ValueError("Production configuration error: MONGO_URL must be explicitly configured.")

        if not os.getenv("DB_NAME", "").strip():
            raise ValueError("Production configuration error: DB_NAME must be explicitly configured.")

        # 2. Demo user seeding prohibition
        raw_seed = os.getenv("SEED_DEMO_USERS", "").lower().strip()
        if raw_seed in ("true", "1", "yes"):
            raise ValueError("Production configuration error: SEED_DEMO_USERS cannot be enabled in production mode.")

        # 3. Telegram Webhook validation if webhook configured
        webhook_url = os.getenv("TELEGRAM_PUBLIC_WEBHOOK_URL", "").strip()
        webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()

        if webhook_url or webhook_secret:
            if not webhook_url:
                raise ValueError(
                    "Production configuration error: TELEGRAM_PUBLIC_WEBHOOK_URL is required when webhook mode is used."
                )
            if not webhook_secret:
                raise ValueError(
                    "Production configuration error: TELEGRAM_WEBHOOK_SECRET is required when webhook mode is used."
                )
            parsed_webhook = urlsplit(webhook_url)
            try:
                parsed_webhook.port
            except ValueError as exc:
                raise ValueError(
                    "Production configuration error: TELEGRAM_PUBLIC_WEBHOOK_URL contains an invalid port."
                ) from exc
            if (
                parsed_webhook.scheme != "https"
                or not parsed_webhook.hostname
                or parsed_webhook.username
                or parsed_webhook.password
                or parsed_webhook.query
                or parsed_webhook.fragment
                or parsed_webhook.path != "/api/v1/telegram/webhook"
            ):
                raise ValueError(
                    "Production configuration error: TELEGRAM_PUBLIC_WEBHOOK_URL must be a valid HTTPS URL ending in /api/v1/telegram/webhook."
                )
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", webhook_secret):
                raise ValueError(
                    "Production configuration error: TELEGRAM_WEBHOOK_SECRET contains unsupported characters or length."
                )

        # 4. CORS origins validation
        get_cors_origins()
