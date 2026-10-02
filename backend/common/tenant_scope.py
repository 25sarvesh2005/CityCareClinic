"""
─────────────────────────────────────────────────────────────────────────────
File        : common/tenant_scope.py
Purpose     : FastAPI dependency that enforces multi-tenant hospital scoping.

Responsibilities:
    - Extract hospital_id from the decoded JWT payload
    - Enforce that roles which MUST be bound to a hospital (DOCTOR,
      HOSPITAL_OWNER) always carry a non-null hospital_id in their token
    - Raise 403 immediately if a scoped role has no hospital_id, preventing
      any unscoped query from reaching the database layer

Design Rule:
    Controllers and CRUDs must NEVER derive the tenant scope from request
    body fields. All tenant information flows from the JWT → this dependency
    → controller → CRUD. This makes it structurally impossible for a client
    to forge a cross-tenant access attempt by injecting a different
    hospital_id into a request body.

Roles & Scoping:
    PATIENT        → hospital_id may be None (single-tenant patients are not
                      yet scoped; multi-tenant patient scoping is Phase 3)
    DOCTOR         → hospital_id REQUIRED — 403 if missing
    HOSPITAL_OWNER → hospital_id REQUIRED — 403 if missing
    SUPER_ADMIN    → hospital_id is always None; cross-tenant access is
                      granted by the SUPER_ADMIN role itself, not by a
                      hospital_id value

Usage:
    from common.tenant_scope import get_hospital_scope

    @router.get("/v1/some-endpoint")
    async def my_endpoint(scope: dict = Depends(get_hospital_scope)):
        hospital_id = scope["hospital_id"]   # guaranteed non-None here
        user_id     = scope["user_id"]
        role        = scope["role"]

Flow:
    oauth2_scheme (Bearer token)
        ↓
    get_current_user() — decodes + validates JWT
        ↓
    get_hospital_scope() — enforces hospital_id presence for scoped roles
        ↓
    Controller receives fully-validated scope dict

Used By:
    - core/apis/routes/appointment_routes.py  (Phase 2)
    - core/apis/routes/doctor_routes.py       (Phase 2)
─────────────────────────────────────────────────────────────────────────────
"""

from fastapi import Depends, HTTPException, status

from common.auth import get_current_user
from common.logger import get_logger
from core.constants import UserRole

logger = get_logger(__name__)

# Roles that are always bound to a specific hospital tenant.
# If a token for these roles is missing hospital_id, the token is malformed
# or was issued before the multi-tenant migration — reject it immediately.
_HOSPITAL_SCOPED_ROLES: frozenset[str] = frozenset(
    {UserRole.DOCTOR.value, UserRole.HOSPITAL_OWNER.value}
)


async def get_hospital_scope(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    FastAPI dependency that extracts and validates the hospital tenant scope.

    For DOCTOR and HOSPITAL_OWNER roles, hospital_id MUST be present in the
    JWT payload. For PATIENT and SUPER_ADMIN, hospital_id may be None — the
    caller is responsible for handling the None case appropriately.

    Args:
        current_user (dict): Decoded JWT payload injected by get_current_user.
                             Expected keys: user_id, email, name, role, hospital_id.

    Returns:
        dict: The same current_user payload, guaranteed to have a non-None
              hospital_id when the role is DOCTOR or HOSPITAL_OWNER.

    Raises:
        HTTPException 403: If a hospital-scoped role (DOCTOR, HOSPITAL_OWNER)
                           has a missing or null hospital_id in their token.
                           This indicates a malformed or pre-migration JWT.
    """
    role: str = current_user.get("role", "")
    hospital_id: str | None = current_user.get("hospital_id")

    if role in _HOSPITAL_SCOPED_ROLES and not hospital_id:
        logger.warning(
            "Tenant scope violation — role '%s' for user '%s' has no hospital_id in JWT. "
            "Token is malformed or was issued before multi-tenant migration.",
            role,
            current_user.get("email"),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your account is not associated with a hospital. "
                "Please contact your administrator."
            ),
        )

    logger.debug(
        "Hospital scope resolved — role: '%s', hospital_id: '%s', user: '%s'",
        role,
        hospital_id,
        current_user.get("email"),
    )
    return current_user
