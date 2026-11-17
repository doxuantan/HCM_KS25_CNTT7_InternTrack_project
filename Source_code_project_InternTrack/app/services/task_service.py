from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.task import Task, TaskStatus
from app.models.task_assignment import TaskAssignment
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
            detail="Không tìm thấy nhiệm vụ.",
        )
    return task


def _assert_task_manager(db: Session, task: Task, user: User) -> None:
    if user.role == UserRole.ADMIN:
        return

    if user.role == UserRole.SUPERVISOR:
        lecturer_id = db.scalar(
            select(Lecturer.id).where(Lecturer.user_id == user.id)
        )
        if lecturer_id is not None:
            owns_team = db.scalar(
                select(Team.id).where(
                    Team.id == task.team_id,
                    Team.supervisor_id == lecturer_id,
                )
            )
            if owns_team is not None:
                return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bạn không có quyền quản lý nhiệm vụ này.",
    )


def _local_naive_datetime(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


def create_task(db: Session, data: TaskCreate, user: User) -> Task:
    team = db.get(Team, data.team_id)
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy nhóm của nhiệm vụ.",
        )

    deadline = _local_naive_datetime(data.deadline)
    if deadline.date() < data.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Hạn hoàn thành phải cùng hoặc sau ngày bắt đầu.",
        )
    if deadline < datetime.now():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Hạn hoàn thành không được nằm trong quá khứ.",
        )

    task = Task(
        team_id=data.team_id,
        title=data.title,
        description=data.description,
        task_type=data.task_type,
        priority=data.priority,
        status=TaskStatus.TODO,
        start_date=data.start_date,
        deadline=deadline,
        created_by=user.id,
    )
    _assert_task_manager(db, task, user)

    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def assign_task(
    db: Session,
    task_id: int,
    data: TaskAssign,
    user: User,
) -> Task:
    task = _get_task(db, task_id)
    _assert_task_manager(db, task, user)

    student = db.get(Student, data.student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sinh viên được giao nhiệm vụ.",
        )

    assignee = db.get(User, student.user_id)
    if assignee is None or assignee.role != UserRole.STUDENT or not assignee.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Tài khoản được giao nhiệm vụ không hợp lệ hoặc đã bị vô hiệu hóa.",
        )

    is_member = db.scalar(
        select(TeamMember.id).where(
            TeamMember.team_id == task.team_id,
            TeamMember.student_id == student.id,
        )
    )
    if is_member is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Sinh viên được giao phải là thành viên của nhóm nhiệm vụ.",
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
            detail="Sinh viên đã được giao nhiệm vụ này.",
        )

    db.add(
        TaskAssignment(
            task_id=task.id,
            student_id=student.id,
            assigned_by=user.id,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể phân công nhiệm vụ cho sinh viên này.",
        ) from None

    db.refresh(task)
    return task


def update_task_status(
    db: Session,
    task_id: int,
    data: TaskStatusUpdate,
    user: User,
) -> Task:
    task = _get_task(db, task_id)
    if user.role == UserRole.STUDENT:
        student_id = db.scalar(
            select(Student.id).where(Student.user_id == user.id)
        )
        is_assigned = student_id is not None and db.scalar(
            select(TaskAssignment.id).where(
                TaskAssignment.task_id == task.id,
                TaskAssignment.student_id == student_id,
            )
        )
        if not is_assigned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không được giao nhiệm vụ này.",
            )
    else:
        _assert_task_manager(db, task, user)

    if task.status != TaskStatus.TODO or data.status != TaskStatus.DONE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chỉ cho phép chuyển trạng thái từ TODO sang DONE.",
        )

    task.status = TaskStatus.DONE
    db.commit()
    db.refresh(task)
    return task


def update_task_progress(
    db: Session,
    task_id: int,
    data: TaskProgressUpdate,
    user: User,
) -> TaskAssignment:
    task = _get_task(db, task_id)
    if user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ thành viên được giao nhiệm vụ mới có thể cập nhật tiến độ.",
        )

    student_id = db.scalar(
        select(Student.id).where(Student.user_id == user.id)
    )
    if student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản chưa được liên kết với hồ sơ sinh viên.",
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
            detail="Bạn không được giao nhiệm vụ này.",
        )

    assignment.progress = data.progress
    db.commit()
    db.refresh(assignment)
    return assignment