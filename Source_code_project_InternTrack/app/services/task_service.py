from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.task import Task, TaskStatus
from app.models.task_assignment import TaskAssignment
from app.models.task_history import TaskHistory
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole
from app.schemas.task import (
    TaskAssign,
    TaskCreate,
    TaskProgressUpdate,
    TaskStatusUpdate,
)


def _get_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )
    return task


def _require_team_manager(db: Session, team: Team, user: User) -> None:
    if user.role == UserRole.ADMIN:
        return
    lecturer_id = db.scalar(
        select(Lecturer.id).where(Lecturer.user_id == user.id)
    )
    if (
        user.role != UserRole.SUPERVISOR
        or lecturer_id is None
        or team.supervisor_id != lecturer_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage tasks for this team.",
        )


def _commit(db: Session, error_detail: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The task operation conflicts with existing data.",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail,
        ) from None


def create_task(db: Session, data: TaskCreate, user: User) -> Task:
    team = db.get(Team, data.team_id)
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found.",
        )
    _require_team_manager(db, team, user)

    deadline = data.deadline
    now = datetime.now(deadline.tzinfo) if deadline.tzinfo else datetime.now()
    if deadline < now:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Deadline must not be in the past.",
        )

    task = Task(**data.model_dump(), created_by=user.id)
    db.add(task)
    _commit(db, "Unable to create the task at this time.")
    db.refresh(task)
    return task


def assign_task(
    db: Session,
    task_id: int,
    data: TaskAssign,
    user: User,
) -> TaskAssignment:
    task = _get_task(db, task_id)
    _require_team_manager(db, task.team, user)

    student = db.scalar(
        select(Student)
        .options(joinedload(Student.user))
        .where(Student.id == data.student_id)
    )
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found.",
        )
    if (
        student.user is None
        or not student.user.is_active
        or student.user.role != UserRole.STUDENT
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tasks can only be assigned to active student accounts.",
        )

    team_member = db.scalar(
        select(TeamMember.id).where(
            TeamMember.team_id == task.team_id,
            TeamMember.student_id == student.id,
        )
    )
    if team_member is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The student is not a member of this team.",
        )

    existing_assignment = db.scalar(
        select(TaskAssignment.id).where(
            TaskAssignment.task_id == task.id,
            TaskAssignment.student_id == student.id,
        )
    )
    if existing_assignment is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The student is already assigned to this task.",
        )

    assignment = TaskAssignment(
        task_id=task.id,
        student_id=student.id,
        assigned_by=user.id,
    )
    db.add(assignment)
    _commit(db, "Unable to assign the task at this time.")
    db.refresh(assignment)
    return assignment


def update_task_status(
    db: Session,
    task_id: int,
    data: TaskStatusUpdate,
    user: User,
) -> Task:
    task = _get_task(db, task_id)
    _require_team_manager(db, task.team, user)

    if task.status != TaskStatus.TODO or data.status != TaskStatus.DONE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A task can only transition from TODO to DONE.",
        )

    task.status = TaskStatus.DONE
    db.add(
        TaskHistory(
            task_id=task.id,
            user_id=user.id,
            old_status=TaskStatus.TODO.value,
            new_status=TaskStatus.DONE.value,
            description="Task status updated.",
        )
    )
    _commit(db, "Unable to update the task status at this time.")
    db.refresh(task)
    return task


def update_task_progress(
    db: Session,
    task_id: int,
    data: TaskProgressUpdate,
    user: User,
) -> TaskAssignment:
    task = _get_task(db, task_id)
    student_id = db.scalar(
        select(Student.id).where(Student.user_id == user.id)
    )
    if student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an assigned student can update task progress.",
        )

    assignment = db.scalar(
        select(TaskAssignment).where(
            TaskAssignment.task_id == task.id,
            TaskAssignment.student_id == student_id,
        )
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this task.",
        )

    assignment.progress = data.progress
    _commit(db, "Unable to update task progress at this time.")
    db.refresh(assignment)
    return assignment