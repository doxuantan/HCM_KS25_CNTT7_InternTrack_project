import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserRole


_EMAIL_PATTERN = re.compile(
    r"^[A-Z0-9!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[A-Z0-9!#$%&'*+/=?^_`{|}~-]+)*@"
    r"(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"
    r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?$",
    re.IGNORECASE,
)


def _normalize_email(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("A valid email address is required.")

    email = value.strip()
    if not _EMAIL_PATTERN.fullmatch(email):
        raise ValueError("A valid email address is required.")
    return email.lower()


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_and_validate_email(cls, value: str) -> str:
        return _normalize_email(value)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=100)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_and_validate_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("full_name", mode="before")
    @classmethod
    def trim_full_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool


AuthenticatedUser = UserResponse


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class LogoutResponse(BaseModel):
    message: str = (
        "Logout acknowledged. This stateless access token remains valid until it expires."
    )