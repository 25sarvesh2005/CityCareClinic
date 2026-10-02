import logging

from fastapi import APIRouter, HTTPException, status

from core.apis.schemas.auth_schema import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from core.controllers.auth_controller import AuthController

router = APIRouter(tags=["Authentication"])


@router.post(
    "/v1/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient account",
)
async def signup(signup_request: SignupRequest) -> UserResponse:
    """
    Register a new user account.

    Args:
        signup_request: Validated signup payload. FastAPI rejects malformed
            bodies with ``422`` before this function is entered.

    Returns:
        UserResponse: Details of the created user account.

    Raises:
        HTTPException:
            * ``409 Conflict`` — account with this email address already exists.
            * ``422 Unprocessable Entity`` — payload validation error.
            * ``500 Internal Server Error`` — any unexpected failure.
    """
    try:
        logging.info("Calling POST /v1/signup endpoint")
        # `await` is required: signup is an async controller function. Handing back
        # a coroutine object rather than the result causes FastAPI to fail serialization.
        result = await AuthController().signup(signup_request)
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed to register user: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )


@router.post(
    "/v1/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login and receive JWT token",
)
async def login(login_request: LoginRequest) -> TokenResponse:
    """
    Authenticate a user and issue a JWT access token.

    Args:
        login_request: Validated login payload (email, password). FastAPI rejects
            malformed bodies with ``422`` before this function is entered.

    Returns:
        TokenResponse: Access token, token_type, user role, and name.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — invalid email address or password.
            * ``422 Unprocessable Entity`` — payload validation error.
            * ``500 Internal Server Error`` — any unexpected failure.
    """
    try:
        logging.info("Calling POST /v1/login endpoint")
        # `await` is required: login is an async controller function. Calling it
        # without awaiting hands back a coroutine object rather than the result.
        result = await AuthController().login(login_request)
        return result
    except HTTPException:
        raise
    except Exception as error:
        logging.error("Failed user login: %s", str(error), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )
