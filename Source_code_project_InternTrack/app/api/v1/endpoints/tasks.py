from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.task import TaskPriority, TaskStatus
from app.schemas.task import (
    TaskAssign,
    TaskAssignmentResponse,
    TaskCreate,
    TaskProgressUpdate,
    TaskResponse,
    TaskStatusUpdate,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskReviewUpdate,
    TaskListResponse,
    TaskResponse,
    TaskReviewResponse,
    TaskUpdate,
)
from app.services import task_service


router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=TaskListResponse)
def list_tasks(
    team: int | None = Query(default=None, gt=0),
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    assignee: int | None = Query(default=None, gt=0),
    priority: TaskPriority | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    deadline_from: datetime | None = Query(default=None),
    deadline_to: datetime | None = Query(default=None),
    sort: str = Query(default="created_desc", pattern="^(title_asc|title_desc|created_asc|created_desc|deadline_asc|deadline_desc)$"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return task_service.list_tasks(
        db,
        current_user,
        team=team,
        status=status_filter,
        assignee=assignee,
        priority=priority,
        q=q,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        sort=sort,
        page=page,
        limit=limit,
    )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    return task_service.get_task(db, task_id, current_user)


@router.put("/{task_id}", response_model=TaskResponse)
@router.patch("/{task_id}", response_model=TaskResponse, include_in_schema=False)
def update_task(
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    return task_service.update_task(db, task_id, data, current_user)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    task_service.delete_task(db, task_id, current_user)


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
@router.post("/{task_id}/assign", response_model=TaskResponse, include_in_schema=False)
def assign_task(
    task_id: int,
    data: TaskAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    return task_service.assign_task(db, task_id, data, current_user)


@router.put("/{task_id}/status", response_model=TaskResponse)
@router.patch("/{task_id}/status", response_model=TaskResponse, include_in_schema=False)
def update_task_status(
    task_id: int,
    data: TaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    return task_service.update_task_status(db, task_id, data, current_user)


@router.patch("/{task_id}/progress", response_model=TaskAssignmentResponse)
@router.put("/{task_id}/progress", response_model=TaskAssignmentResponse)
def update_task_progress(
    task_id: int,
    data: TaskProgressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskAssignmentResponse:
    return task_service.update_task_progress(db, task_id, data, current_user)


@router.get("/{task_id}/progress", response_model=TaskAssignmentResponse)
def get_task_progress(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskAssignmentResponse:
    return task_service.get_task_progress(db, task_id, current_user)


@router.post("/{task_id}/review", response_model=TaskReviewResponse)
def review_task(
    task_id: int,
    data: TaskReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return task_service.review_task(db, task_id, data, current_user)


#Task Comment
@router.post(
    "/{task_id}/comments",
    response_model=TaskCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task_comment(
    task_id: int,
    data: TaskCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskCommentResponse:
    return task_service.create_task_comment(
        db, task_id, data, current_user
    )


@router.get(
    "/{task_id}/comments",
    response_model=list[TaskCommentResponse],
)
def get_task_comments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TaskCommentResponse]:
    return task_service.get_task_comments(
        db, task_id, current_user
    )
