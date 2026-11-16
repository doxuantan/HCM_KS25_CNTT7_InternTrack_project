from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password
from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def _user_query():
    return select(User).options(
        selectinload(User.student),
        selectinload(User.lecturer),
    )


def get_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    try:
        statement = _user_query().order_by(User.id).offset(skip).limit(limit)
        return list(db.scalars(statement).all())
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve users at this time.",
        ) from None


def get_user(db: Session, user_id: int) -> User:
    try:
        user = db.scalar(_user_query().where(User.id == user_id))
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve the user at this time.",
        ) from None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


def create_user(db: Session, data: UserCreate) -> User:
    try:
        existing_user_id = db.scalar(
            select(User.id).where(func.lower(User.email) == data.email)
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create the account at this time.",
        ) from None

    if existing_user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    try:
        password_hash = hash_password(data.password)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Password must not exceed 72 UTF-8 bytes.",
        ) from None

    user = User(
        email=data.email,
        password_hash=password_hash,
        full_name=data.full_name,
        phone=data.phone,
        avatar=data.avatar,
        role=data.role,
    )

    try:
        db.add(user)
        db.flush()
        if data.student_profile is not None:
            user.student = Student(
                **data.student_profile.model_dump(),
                user_id=user.id,
            )
        if data.lecturer_profile is not None:
            user.lecturer = Lecturer(
                **data.lecturer_profile.model_dump(),
                user_id=user.id,
            )
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The email or profile code is already in use.",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create the account at this time.",
        ) from None


def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    user = get_user(db, user_id)
    update_data = data.model_dump(exclude_unset=True)

    if "email" in update_data and update_data["email"] != user.email:
        try:
            existing_user_id = db.scalar(
                select(User.id).where(
                    func.lower(User.email) == update_data["email"],
                    User.id != user_id,
                )
            )
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to update the user at this time.",
            ) from None
        if existing_user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

    for field_name, value in update_data.items():
        setattr(user, field_name, value)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update the user at this time.",
        ) from None
    return user


def update_user_status(db: Session, user_id: int, is_active: bool) -> User:
    user = get_user(db, user_id)
    user.is_active = is_active

    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update the user status at this time.",
        ) from None
    return user


def delete_user(db: Session, user_id: int) -> None:
    try:
        user = db.get(User, user_id)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve the user at this time.",
        ) from None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    try:
        db.delete(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user is referenced by other records and cannot be deleted.",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete the user at this time.",
        ) from None