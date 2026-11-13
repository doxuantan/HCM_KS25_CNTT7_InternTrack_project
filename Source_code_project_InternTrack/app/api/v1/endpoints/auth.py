from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User, UserRole
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    try:
        existing_user_id = db.scalar(
            select(User.id).where(func.lower(User.email) == payload.email)
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
        password_hash = hash_password(payload.password)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Password must not exceed 72 UTF-8 bytes.",
        ) from None

    user = User(
        email=payload.email,
        password_hash=password_hash,
        full_name=payload.full_name,
        role=UserRole.STUDENT,
        is_active=True,
    )

    try:
        db.add(user)
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
            detail="Unable to create the account at this time.",
        ) from None

    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(
        select(User).where(func.lower(User.email) == payload.email)
    )

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    return TokenResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    _current_user: User = Depends(get_current_user),
) -> LogoutResponse:
    return LogoutResponse()


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)