from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.user import UserRole
from app.schemas.auth import _normalize_email


class StudentProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_code: str = Field(min_length=1, max_length=30)
    class_name: str | None = Field(default=None, max_length=100)
    major: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("student_code", mode="before")
    @classmethod
    def trim_student_code(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class LecturerProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lecturer_code: str = Field(min_length=1, max_length=30)
    department: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("lecturer_code", mode="before")
    @classmethod
    def trim_lecturer_code(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=100)
    role: UserRole
    phone: str | None = Field(default=None, max_length=20)
    avatar: str | None = Field(default=None, max_length=500)
    student_profile: StudentProfileCreate | None = None
    lecturer_profile: LecturerProfileCreate | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_and_validate_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("full_name", mode="before")
    @classmethod
    def trim_full_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_role_profile(self) -> "UserCreate":
        if self.role == UserRole.STUDENT:
            if self.student_profile is None or self.lecturer_profile is not None:
                raise ValueError(
                    "A STUDENT account requires only a student_profile."
                )
        elif self.role == UserRole.SUPERVISOR:
            if self.lecturer_profile is None or self.student_profile is not None:
                raise ValueError(
                    "A SUPERVISOR account requires only a lecturer_profile."
                )
        elif self.student_profile is not None or self.lecturer_profile is not None:
            raise ValueError("ADMIN accounts cannot include a student or lecturer profile.")
        return self


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = Field(default=None, min_length=1, max_length=255)
    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    avatar: str | None = Field(default=None, max_length=500)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_and_validate_email(cls, value: str | None) -> str | None:
        return _normalize_email(value) if value is not None else value

    @field_validator("full_name", mode="before")
    @classmethod
    def trim_full_name(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_update_fields(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one user field must be provided.")
        for field_name in ("email", "full_name"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class UserStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class StudentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_code: str
    class_name: str | None
    major: str | None
    phone: str | None


class LecturerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lecturer_code: str
    department: str | None
    phone: str | None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str | None
    avatar: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime | None
    student_profile: StudentProfileResponse | None = Field(
        default=None,
        validation_alias="student",
    )
    lecturer_profile: LecturerProfileResponse | None = Field(
        default=None,
        validation_alias="lecturer",
    )