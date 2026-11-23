"""Explicitly seed the development-only InternTrack administrator.

Run with:
    python -m app.db.seed_admin

Requires APP_ENV=development and DEFAULT_ADMIN_PASSWORD in the environment.
"""

import sys

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.user import User, UserRole


DEFAULT_ADMIN_EMAIL = "admin@interntrack.local"
DEFAULT_ADMIN_FULL_NAME = "InternTrack Developer Admin"


def _require_development_environment() -> None:
    if settings.APP_ENV != "development":
        raise RuntimeError(
            "Default ADMIN seeding is allowed only when APP_ENV=development."
        )


def _get_existing_admin(db: Session) -> User | None:
    user = db.scalar(
        select(User).where(func.lower(User.email) == DEFAULT_ADMIN_EMAIL)
    )
    if user is not None and user.role != UserRole.ADMIN:
        raise RuntimeError(
            "The default ADMIN email already belongs to a non-ADMIN account; "
            "no changes were made."
        )
    return user


def seed_default_admin(db: Session) -> bool:
    _require_development_environment()

    existing_user = _get_existing_admin(db)
    if existing_user is not None:
        print("Default development ADMIN already exists; no changes were made.")
        return False

    password_setting = settings.DEFAULT_ADMIN_PASSWORD
    if password_setting is None or not password_setting.get_secret_value():
        raise RuntimeError(
            "Set DEFAULT_ADMIN_PASSWORD before seeding the development ADMIN."
        )

    password = password_setting.get_secret_value()
    if len(password) < 8:
        raise ValueError("DEFAULT_ADMIN_PASSWORD must be at least 8 characters.")
    try:
        password_hash = hash_password(password)
    except ValueError:
        raise ValueError(
            "DEFAULT_ADMIN_PASSWORD must not exceed 72 UTF-8 bytes."
        ) from None

    user = User(
        email=DEFAULT_ADMIN_EMAIL,
        password_hash=password_hash,
        full_name=DEFAULT_ADMIN_FULL_NAME,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_user = _get_existing_admin(db)
        if existing_user is None:
            raise
        print("Default development ADMIN already exists; no changes were made.")
        return False
    except SQLAlchemyError:
        db.rollback()
        raise

    print(f"Created development ADMIN account: {DEFAULT_ADMIN_EMAIL}")
    return True


def main() -> int:
    try:
        _require_development_environment()

        db = SessionLocal()
        try:
            seed_default_admin(db)
        finally:
            db.close()
        return 0
    except SQLAlchemyError:
        print(
            "Seed failed: cannot connect to or operate on the database. "
            "Check that MySQL is running and that DATABASE_URL in .env is correct.",
            file=sys.stderr,
        )
        return 1
    except (RuntimeError, ValueError) as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
