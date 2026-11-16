from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.permissions import require_role
from app.models.user import UserRole
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserStatusUpdate,
    UserUpdate,
)
from app.services import user_service


router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)


@router.get("", response_model=list[UserResponse])
def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[UserResponse]:
    return user_service.get_users(db, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserResponse:
    return user_service.get_user(db, user_id)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
) -> UserResponse:
    return user_service.create_user(db, payload)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
) -> UserResponse:
    return user_service.update_user(db, user_id, payload)


@router.patch("/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
) -> UserResponse:
    return user_service.update_user_status(db, user_id, payload.is_active)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_user(user_id: int, db: Session = Depends(get_db)) -> Response:
    user_service.delete_user(db, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)