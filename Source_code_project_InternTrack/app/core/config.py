from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    APP_ENV: str = Field(default="production", min_length=1)
    DATABASE_URL: str = Field(min_length=1)
    SECRET_KEY: SecretStr = Field(min_length=32)
    DEFAULT_ADMIN_PASSWORD: SecretStr | None = None
    SAMPLE_USER_PASSWORD: SecretStr | None = None
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, gt=0)
    MAX_ATTACHMENT_SIZE_MB: int = Field(default=10, gt=0)
    ATTACHMENT_STORAGE_DIR: Path = Path("storage/uploads")
    ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5500",
            "http://localhost:5500",
        ]
    )

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def validate_allowed_origins(cls, origins: list[str]) -> list[str]:
        if not origins:
            raise ValueError("ALLOWED_ORIGINS must contain at least one origin.")
        for origin in origins:
            parsed = urlsplit(origin)
            try:
                parsed.port
            except ValueError:
                raise ValueError("ALLOWED_ORIGINS must contain valid origin URLs.") from None
            if (
                origin != origin.strip()
                or origin == "*"
                or parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "ALLOWED_ORIGINS entries must be exact http(s) origins without paths or wildcards."
                )
        return origins

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def attachment_storage_path(self) -> Path:
        storage_path = self.ATTACHMENT_STORAGE_DIR
        if not storage_path.is_absolute():
            storage_path = PROJECT_ROOT / storage_path
        return storage_path.resolve()


settings = Settings()
