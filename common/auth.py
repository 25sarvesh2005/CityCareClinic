"""
─────────────────────────────────────────────────────────────────────────────
File        : common/auth.py
Purpose     : Authentication and authorization utilities for the CityCare
              Clinic backend.

Responsibilities:
    - Password hashing and verification via bcrypt
    - JWT access token creation and decoding
    - FastAPI dependency for extracting the current authenticated user
    - FastAPI dependency for enforcing doctor-only access (RBAC)

Flow:
    Client Request
        ↓
    OAuth2PasswordBearer extracts Bearer token from Authorization header
        ↓
    get_current_user() decodes JWT → returns UserModel payload
        ↓
    Optional: require_doctor() checks role → raises 403 if patient

Authentication:
    - Algorithm : HS256 (configurable via JWT_ALGORITHM env var)
    - Secret    : JWT_SECRET env var
    - Expiry    : JWT_EXPIRE_MINUTES env var (default 60 minutes)

Used By:
    - core/apis/routes/*.py (as FastAPI dependencies)

Returns:
    - create_access_token() → str (JWT token)
    - get_current_user()    → dict (decoded JWT payload)
    - require_doctor()      → dict (same payload, only if role == doctor)

Raises:
    - 401 Unauthorized  — missing or invalid token
    - 403 Forbidden     — authenticated but insufficient role
─────────────────────────────────────────────────────────────────────────────
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from common.logger import get_logger

# ─── Logger ───────────────────────────────────────────────────────────────────

logger = get_logger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

JWT_SECRET: str = os.getenv("JWT_SECRET", "your-super-secret-key-change-in-production")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

import bcrypt

# ─── OAuth2 Scheme ────────────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


# ─── Password Utilities ───────────────────────────────────────────────────────


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Args:
        plain_password (str): The user's raw password from the request body.

    Returns:
        str: A bcrypt-hashed password string safe for database storage.
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compare a plain-text password against its stored bcrypt hash.

    Args:
        plain_password  (str): The raw password from the login request.
        hashed_password (str): The stored hash retrieved from the database.

    Returns:
        bool: True if the passwords match, False otherwise.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False



# ─── JWT Utilities ────────────────────────────────────────────────────────────


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token embedding the given payload data.

    The token is signed with JWT_SECRET using the JWT_ALGORITHM.
    Expiry defaults to JWT_EXPIRE_MINUTES if no explicit delta is provided.

    Args:
        data          (dict)               : Payload claims (e.g. user_id, role, email).
        expires_delta (Optional[timedelta]): Override the default expiry window.

    Returns:
        str: A signed JWT string ready to be sent to the client.
    """
    payload = data.copy()
    expiry = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=JWT_EXPIRE_MINUTES)
    )
    payload.update({"exp": expiry})

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    logger.debug("Access token created for subject: %s", data.get("user_id"))
    return token


def decode_jwt(token: str) -> Optional[dict]:
    """
    Decode a JWT access token safely, returning payload dictionary on success or None on failure.
    """
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


# Alias for compatibility
decodeJWT = decode_jwt


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    Args:
        token (str): The raw Bearer token string from the Authorization header.

    Returns:
        dict: The decoded payload containing user_id, email, role, etc.

    Raises:
        HTTPException 401: If the token is expired, malformed, or invalid.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as error:
        logger.warning("Token decoding failed: %s", str(error))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── FastAPI Dependencies ─────────────────────────────────────────────────────


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    FastAPI dependency that extracts and validates the Bearer token.

    Decodes the JWT and returns the payload dictionary. Identity and tenant
    scope are ALWAYS read from the token — never from the request body.

    Args:
        token (str): Automatically extracted by OAuth2PasswordBearer.

    Returns:
        dict: Decoded JWT payload containing:
            - user_id    (str)           : String ObjectId of the user.
            - email      (str)           : User's email address.
            - role       (str)           : One of: patient, doctor, hospital_owner, super_admin.
            - name       (str)           : User's full name.
            - hospital_id (str | None)  : String ObjectId of the user's hospital tenant.
                                          None for PATIENT and SUPER_ADMIN roles.

    Raises:
        HTTPException 401: If the token is missing, expired, or invalid.
    """
    logger.debug("Authenticating request via Bearer token")
    return decode_access_token(token)


async def require_doctor(current_user: dict = Depends(get_current_user)) -> dict:
    """
    FastAPI dependency that enforces doctor-only access control.

    Wraps get_current_user() and additionally verifies that the
    authenticated user holds the 'doctor' role.

    Args:
        current_user (dict): Injected by get_current_user dependency.

    Returns:
        dict: The same payload if the role is 'doctor'.

    Raises:
        HTTPException 403: If the authenticated user is a patient.
    """
    if current_user.get("role") != "doctor":
        logger.warning(
            "Authorization failure — user '%s' attempted doctor-only endpoint",
            current_user.get("email"),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Doctor role required.",
        )

    logger.debug("Doctor access granted for: %s", current_user.get("email"))
    return current_user


async def require_super_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    FastAPI dependency that enforces super-admin-only access control.

    Wraps get_current_user() and verifies the authenticated user holds
    the 'super_admin' role. Used by all /api/v1/admin/* routes.

    Args:
        current_user (dict): Injected by get_current_user dependency.

    Returns:
        dict: The same payload if the role is 'super_admin'.

    Raises:
        HTTPException 403: If the authenticated user is not a super admin.
    """
    if current_user.get("role") != "super_admin":
        logger.warning(
            "Authorization failure — user '%s' (role: '%s') attempted super-admin endpoint",
            current_user.get("email"),
            current_user.get("role"),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Super admin role required.",
        )

    logger.debug("Super admin access granted for: %s", current_user.get("email"))
    return current_user

