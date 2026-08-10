"""
─────────────────────────────────────────────────────────────────────────────
File        : core/apis/schemas/auth_schema.py
Purpose     : Pydantic request and response schemas for authentication endpoints.

Responsibilities:
    - Validate signup and login request bodies
    - Define structured response models for token and user data
    - Provide Swagger-ready field descriptions and examples

Used By:
    - core/apis/routes/auth_router.py
    - core/controllers/auth_controller.py

Notes:
    These schemas perform only structural validation.
    Business logic (e.g. duplicate email check) lives in the controller.
─────────────────────────────────────────────────────────────────────────────
"""

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    """
    Request body schema for POST /signup.

    Validates that a new user provides a name, a valid email address,
    and a password that meets the minimum length requirement.
    """

    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Full name of the user.",
        examples=["Rahul Sharma"],
    )
    email: EmailStr = Field(
        ...,
        description="A valid, unique email address used for login.",
        examples=["rahul.sharma@email.com"],
    )
    password: str = Field(
        ...,
        min_length=6,
        description="Account password. Minimum 6 characters.",
        examples=["secure123"],
    )


class LoginRequest(BaseModel):
    """
    Request body schema for POST /login.

    Accepts an email and password pair. On success, the response
    contains a JWT access token for subsequent authenticated requests.
    """

    email: EmailStr = Field(
        ...,
        description="Registered email address of the user.",
        examples=["rahul.sharma@email.com"],
    )
    password: str = Field(
        ...,
        description="The user's account password.",
        examples=["secure123"],
    )


class TokenResponse(BaseModel):
    """
    Response schema returned on successful login.

    The access_token must be sent as a Bearer token in the
    Authorization header for all protected endpoints.
    """

    access_token: str = Field(
        ...,
        description="JWT Bearer token. Include in Authorization header as 'Bearer <token>'.",
    )
    token_type: str = Field(default="bearer", description="Token type. Always 'bearer'.")
    role: str = Field(..., description="Role of the authenticated user: 'patient' or 'doctor'.")
    name: str = Field(..., description="Full name of the authenticated user.")
    email: str = Field(..., description="Email address of the authenticated user.")


class UserResponse(BaseModel):
    """
    Response schema returned on successful user registration.

    Does not include the password or hashed_password fields.
    """

    user_id: str = Field(..., description="Unique identifier of the newly created user.")
    name: str = Field(..., description="Full name of the registered user.")
    email: str = Field(..., description="Email address of the registered user.")
    role: str = Field(..., description="Assigned role: 'patient' or 'doctor'.")
    message: str = Field(..., description="Human-readable success message.")
