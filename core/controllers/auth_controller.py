import os
from fastapi import HTTPException, status

from common.auth import create_access_token, hash_password, verify_password
from common.logger import get_logger
from core.apis.schemas.auth_schema import LoginRequest, SignupRequest, TokenResponse, UserResponse
from core.constants import UserRole
from core.cruds.user_crud import create_user, find_user_by_email
from core.database.database import get_engine
from core.models.user_model import UserModel

logger = get_logger(__name__)
DOCTOR_EMAIL: str = os.getenv("DOCTOR_EMAIL", "dr.meera@citycare.com").lower()


class AuthController:
    """Controller handling authentication operations."""

    async def signup(self, signup_request: SignupRequest) -> UserResponse:
        engine = get_engine()
        clean_email = signup_request.email.strip().lower()
        clean_password = signup_request.password.strip()

        existing_user = await find_user_by_email(engine, clean_email)
        if existing_user:
            logger.warning("Signup rejected — email already registered: %s", clean_email)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        assigned_role = (
            UserRole.DOCTOR
            if clean_email == DOCTOR_EMAIL
            else UserRole.PATIENT
        )

        new_user = UserModel(
            name=signup_request.name.strip(),
            email=clean_email,
            hashed_password=hash_password(clean_password),
            role=assigned_role,
        )

        saved_user = await create_user(engine, new_user)
        logger.info("User registered — email: %s, role: %s", saved_user.email, saved_user.role)

        return UserResponse(
            user_id=str(saved_user.id),
            name=saved_user.name,
            email=saved_user.email,
            role=saved_user.role.value,
            message="Account created successfully. You can now log in.",
        )

    async def login(self, login_request: LoginRequest) -> TokenResponse:
        engine = get_engine()
        clean_email = login_request.email.strip().lower()
        clean_password = login_request.password.strip()

        user = await find_user_by_email(engine, clean_email)
        if not user or not verify_password(clean_password, user.hashed_password):
            logger.warning("Login failed for email: %s", clean_email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email address or password.",
            )

        token_payload = {
            "user_id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role.value,
            # hospital_id is None for PATIENT and SUPER_ADMIN roles;
            # populated for DOCTOR and HOSPITAL_OWNER. Always present in
            # the JWT so tenant_scope.py can rely on the key existing.
            "hospital_id": user.hospital_id,
        }

        access_token = create_access_token(token_payload)
        logger.info("Login successful — email: %s", user.email)

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            role=user.role.value,
            name=user.name,
            email=user.email,
        )


# Backward compatibility wrappers
signup_controller = AuthController().signup
login_controller = AuthController().login
