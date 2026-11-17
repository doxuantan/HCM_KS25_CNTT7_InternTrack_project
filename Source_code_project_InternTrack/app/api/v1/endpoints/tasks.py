from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import User, UserRole
from app.schemas.task import (
    TaskAssign,
    TaskAssignmentResponse,
    TaskCreate,
    TaskProgressUpdate,
    TaskResponse,
    TaskStatusUpdate,
)
from app.services import task_service


router = APIRouter(prefix="/tasks", tags=["tasks"])
team_managers = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERVISOR))


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    user: User = team_managers,
) -> TaskResponse:
    return task_service.create_task(db, data, user)


@router.put("/{task_id}/assign", response_model=TaskAssignmentResponse)
def assign_task(
    task_id: int = Path(gt=0),
    data: TaskAssign = ...,
    db: Session = Depends(get_db),
    user: User = team_managers,
) -> TaskAssignmentResponse:
    return task_service.assign_task(db, task_id, data, user)


@router.patch("/{task_id}/status", response_model=TaskResponse)
def update_task_status(
    task_id: int = Path(gt=0),
    data: TaskStatusUpdate = ...,
    db: Session = Depends(get_db),
    user: User = team_managers,
) -> TaskResponse:
    return task_service.update_task_status(db, task_id, data, user)


@router.patch("/{task_id}/progress", response_model=TaskAssignmentResponse)
def update_task_progress(
    task_id: int = Path(gt=0),
    data: TaskProgressUpdate = ...,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskAssignmentResponse:
    return task_service.update_task_progress(db, task_id, data, user)