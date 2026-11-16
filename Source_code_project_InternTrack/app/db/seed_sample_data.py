"""Seed demo accounts for development or test databases.

Run with:
    python -m app.db.seed_sample_data

Set SAMPLE_USER_PASSWORD before running. In development, the existing
development-only admin seeder is reused. In test mode, that admin must already
exist in the test database.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.db.seed_admin import DEFAULT_ADMIN_EMAIL, seed_default_admin
from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.user import User, UserRole


SUPERVISORS = (
    {
        "email": "supervisor01@interntrack.local",
        "full_name": "Nguyen Van An",
        "lecturer_code": "GV-IT-001",
        "department": "Information Technology",
    },
    {
        "email": "supervisor02@interntrack.local",
        "full_name": "Tran Thi Binh",
        "lecturer_code": "GV-IT-002",
        "department": "Information Technology",
    },
)

STUDENTS = (
    {
        "email": "student01@interntrack.local",
        "full_name": "Le Minh Anh",
        "student_code": "SV-2026-001",
        "class_name": "CNTT7",
        "major": "Information Technology",
    },
    {
        "email": "student02@interntrack.local",
        "full_name": "Pham Quoc Bao",
        "student_code": "SV-2026-002",
        "class_name": "CNTT7",
        "major": "Information Technology",
    },
    {
        "email": "student03@interntrack.local",
        "full_name": "Do Thu Chi",
        "student_code": "SV-2026-003",
        "class_name": "CNTT7",
        "major": "Information Technology",
    },
    {
        "email": "student04@interntrack.local",
        "full_name": "Hoang Gia Dung",
        "student_code": "SV-2026-004",
        "class_name": "CNTT7",
        "major": "Information Technology",
    },
    {
        "email": "student05@interntrack.local",
        "full_name": "Vu Hai Yen",
        "student_code": "SV-2026-005",
        "class_name": "CNTT7",
        "major": "Information Technology",
    },
)


def _require_seed_environment() -> None:
    if settings.APP_ENV not in {"development", "test"}:
        raise RuntimeError(
            "Sample data seeding is allowed only when APP_ENV is development or test."
        )


def _get_sample_password() -> str:
    password_setting = settings.SAMPLE_USER_PASSWORD
    if password_setting is None or not password_setting.get_secret_value():
        raise RuntimeError("Set SAMPLE_USER_PASSWORD before seeding sample accounts.")

    password = password_setting.get_secret_value()
    if len(password) < 8:
        raise ValueError("SAMPLE_USER_PASSWORD must be at least 8 characters.")
    try:
        hash_password(password)
    except ValueError:
        raise ValueError(
            "SAMPLE_USER_PASSWORD must not exceed 72 UTF-8 bytes."
        ) from None
    return password


def _find_user(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.lower()))


def _seed_supervisor(db: Session, data: dict[str, str], password: str) -> bool:
    user = _find_user(db, data["email"])
    if user is not None:
        lecturer = db.scalar(
            select(Lecturer).where(Lecturer.user_id == user.id)
        )
        student = db.scalar(select(Student.id).where(Student.user_id == user.id))
        if (
            user.role != UserRole.SUPERVISOR
            or lecturer is None
            or lecturer.lecturer_code != data["lecturer_code"]
            or student is not None
        ):
            raise RuntimeError(
                f"Existing account {data['email']} conflicts with the sample SUPERVISOR."
            )
        print(f"[SKIP] Existing sample SUPERVISOR: {data['email']}")
        return False

    code_owner = db.scalar(
        select(Lecturer.id).where(
            func.lower(Lecturer.lecturer_code) == data["lecturer_code"].lower()
        )
    )
    if code_owner is not None:
        raise RuntimeError(
            f"Lecturer code {data['lecturer_code']} is already assigned."
        )

    user = User(
        email=data["email"],
        password_hash=hash_password(password),
        full_name=data["full_name"],
        role=UserRole.SUPERVISOR,
        is_active=True,
    )
    user.lecturer = Lecturer(
        lecturer_code=data["lecturer_code"],
        department=data["department"],
    )
    db.add(user)
    db.flush()
    print(f"[CREATE] Sample SUPERVISOR: {data['email']}")
    return True


def _seed_student(db: Session, data: dict[str, str], password: str) -> bool:
    user = _find_user(db, data["email"])
    if user is not None:
        student = db.scalar(select(Student).where(Student.user_id == user.id))
        lecturer = db.scalar(select(Lecturer.id).where(Lecturer.user_id == user.id))
        if (
            user.role != UserRole.STUDENT
            or student is None
            or student.student_code != data["student_code"]
            or lecturer is not None
        ):
            raise RuntimeError(
                f"Existing account {data['email']} conflicts with the sample STUDENT."
            )
        print(f"[SKIP] Existing sample STUDENT: {data['email']}")
        return False

    code_owner = db.scalar(
        select(Student.id).where(
            func.lower(Student.student_code) == data["student_code"].lower()
        )
    )
    if code_owner is not None:
        raise RuntimeError(
            f"Student code {data['student_code']} is already assigned."
        )

    user = User(
        email=data["email"],
        password_hash=hash_password(password),
        full_name=data["full_name"],
        role=UserRole.STUDENT,
        is_active=True,
    )
    user.student = Student(
        student_code=data["student_code"],
        class_name=data["class_name"],
        major=data["major"],
    )
    db.add(user)
    db.flush()
    print(f"[CREATE] Sample STUDENT: {data['email']}")
    return True


def _ensure_admin_exists(db: Session) -> None:
    if settings.APP_ENV == "development":
        seed_default_admin(db)
        return

    admin = _find_user(db, DEFAULT_ADMIN_EMAIL)
    if admin is None or admin.role != UserRole.ADMIN:
        raise RuntimeError(
            "APP_ENV=test requires an existing default ADMIN; "
            "use the existing development-only admin seeder with the test database."
        )


def _seed_sample_accounts(db: Session, password: str) -> int:
    created_count = 0
    for data in SUPERVISORS:
        created_count += _seed_supervisor(db, data, password)
    for data in STUDENTS:
        created_count += _seed_student(db, data, password)
    return created_count


def main() -> None:
    _require_seed_environment()
    sample_password = _get_sample_password()
    db = SessionLocal()

    try:
        _ensure_admin_exists(db)
        created_count = _seed_sample_accounts(db, sample_password)
        db.commit()
        print(
            "Sample data seed complete. "
            f"Created {created_count} supervisor/student accounts."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
