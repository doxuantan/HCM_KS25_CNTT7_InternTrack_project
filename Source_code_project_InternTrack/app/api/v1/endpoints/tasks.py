from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.task import (
    TaskAssign,
    TaskAssignmentResponse,
    TaskCreate,
    TaskProgressUpdate,
    TaskResponse,
    TaskStatusUpdate,
)
from app.services import task_service


router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    return task_service.create_task(db, data, current_user)


@router.put("/{task_id}/assign", response_model=TaskResponse)
def assign_task(
    task_id: int,
    data: TaskAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    return task_service.assign_task(db, task_id, data, current_user)


@router.patch("/{task_id}/status", response_model=TaskResponse)
def update_task_status(
    task_id: int,
    data: TaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    return task_service.update_task_status(db, task_id, data, current_user)


@router.patch("/{task_id}/progress", response_model=TaskAssignmentResponse)
def update_task_progress(
    task_id: int,
    data: TaskProgressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskAssignmentResponse:
    return task_service.update_task_progress(db, task_id, data, current_user)