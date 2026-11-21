from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.task_comment import TaskComment
from app.models.task_history import TaskHistory

from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.task import Task, TaskStatus
from app.models.task_assignment import TaskAssignment, AssignmentStatus
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole
from app.schemas.task import (
    TaskAssign,
    TaskCreate,
    TaskProgressUpdate,
    TaskStatusUpdate,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskReviewUpdate,
    TaskReviewStatus,
    TaskResponse,
)
from app.services.notification_service import notify_task_assigned


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


def list_tasks(
    db: Session,
    user: User,
    *,
    team: int | None = None,
    status: TaskStatus | None = None,
    assignee: int | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    statement = select(Task)

    if user.role == UserRole.ADMIN:
        pass
    elif user.role == UserRole.SUPERVISOR:
        lecturer_id = db.scalar(
            select(Lecturer.id).where(Lecturer.user_id == user.id)
        )
        if lecturer_id is None:
            return {"items": [], "total": 0, "page": page, "limit": limit, "total_pages": 0}
        statement = statement.join(Team, Team.id == Task.team_id).where(
            Team.supervisor_id == lecturer_id
        )
    elif user.role == UserRole.STUDENT:
        student_id = db.scalar(
            select(Student.id).where(Student.user_id == user.id)
        )
        if student_id is None:
            return {"items": [], "total": 0, "page": page, "limit": limit, "total_pages": 0}
        statement = statement.where(
            select(TaskAssignment.id)
            .where(
                TaskAssignment.task_id == Task.id,
                TaskAssignment.student_id == student_id,
            )
            .exists()
        )
    else:
        return {"items": [], "total": 0, "page": page, "limit": limit, "total_pages": 0}

    if team is not None:
        statement = statement.where(Task.team_id == team)
    if status is not None:
        statement = statement.where(Task.status == status)
    if assignee is not None:
        statement = statement.where(
            select(TaskAssignment.id)
            .where(
                TaskAssignment.task_id == Task.id,
                TaskAssignment.student_id == assignee,
            )
            .exists()
        )

    count_statement = select(func.count()).select_from(
        statement.with_only_columns(Task.id).order_by(None).subquery()
    )
    total = db.scalar(count_statement) or 0
    tasks = db.scalars(
        statement.order_by(Task.id.desc()).offset((page - 1) * limit).limit(limit)
    ).unique().all()
    total_pages = (total + limit - 1) // limit if total else 0
    return {
        "items": list(tasks),
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }


def assign_task(
    db: Session,
    task_id: int,
    data: TaskAssign,
    user: User,
) -> Task:
    task = _get_task(db, task_id)
    _assert_task_manager(db, task, user)

    students: list[Student] = []
    for student_id in data.assignee_ids:
        student = db.get(Student, student_id)
        if student is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy sinh viên được giao nhiệm vụ.",
            )
        students.append(student)

    for student in students:
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

    db.add_all(
        TaskAssignment(
            task_id=task.id,
            student_id=student.id,
            assigned_by=user.id,
        )
        for student in students
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
    for student in students:
        notify_task_assigned(
            db,
            student=student,
            task_title=task.title,
            assigned_by=user,
        )
    return task


def review_task(
    db: Session,
    task_id: int,
    data: TaskReviewUpdate,
    user: User,
) -> dict:
    task = _get_task(db, task_id)

    if user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sinh viên không được tự duyệt nhiệm vụ của mình.",
        )

    _assert_task_manager(db, task, user)

    if task.status != TaskStatus.REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chỉ có thể review nhiệm vụ ở trạng thái REVIEW.",
        )

    old_status = task.status
    if data.status == TaskReviewStatus.APPROVED:
        new_status = TaskStatus.DONE
        for assignment in task.assignments:
            assignment.status = AssignmentStatus.DONE
            assignment.progress = 100
        description = "Task review approved."
    else:
        new_status = TaskStatus.IN_PROGRESS
        for assignment in task.assignments:
            assignment.status = AssignmentStatus.IN_PROGRESS
        description = "Task review requires revision."

    if data.comment:
        description = f"{description} {data.comment.strip()}".strip()

    task.status = new_status
    db.add(
        TaskHistory(
            task_id=task.id,
            user_id=user.id,
            old_status=old_status.value,
            new_status=new_status.value,
            description=description,
        )
    )
    db.commit()
    db.refresh(task)

    return {
        "message": (
            "Đã duyệt nhiệm vụ."
            if data.status == TaskReviewStatus.APPROVED
            else "Đã yêu cầu sinh viên sửa lại nhiệm vụ."
        ),
        "status": data.status,
        "task": TaskResponse.model_validate(task),
    }


def update_task_status(
    db: Session,
    task_id: int,
    data: TaskStatusUpdate,
    user: User,
) -> Task:
    task = _get_task(db, task_id)

    old_status = task.status
    new_status = data.status

    # Sinh viên chỉ được cập nhật nhiệm vụ được giao
    if user.role == UserRole.STUDENT:
        student_id = db.scalar(
            select(Student.id).where(Student.user_id == user.id)
        )

        assignment = None

        if student_id is not None:
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

        # Sinh viên chỉ được bắt đầu hoặc gửi duyệt
        allowed_transitions = {
            TaskStatus.TODO: TaskStatus.IN_PROGRESS,
            TaskStatus.IN_PROGRESS: TaskStatus.REVIEW,
        }

        if allowed_transitions.get(old_status) != new_status:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Sinh viên chỉ được chuyển TODO sang IN_PROGRESS "
                       "hoặc IN_PROGRESS sang REVIEW.",
            )

    else:
        # Chỉ người quản lý nhóm hoặc ADMIN được duyệt hoàn thành
        _assert_task_manager(db, task, user)

        if old_status != TaskStatus.REVIEW or new_status != TaskStatus.DONE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Người quản lý chỉ được chuyển trạng thái "
                       "từ REVIEW sang DONE.",
            )

    # Cập nhật trạng thái nhiệm vụ
    task.status = new_status

    # Đồng bộ trạng thái các bản ghi phân công
    for assignment in task.assignments:
        assignment.status = AssignmentStatus(new_status.value)

        if new_status == TaskStatus.DONE:
            assignment.progress = 100

    # Ghi lịch sử thay đổi trạng thái
    history = TaskHistory(
        task_id=task.id,
        user_id=user.id,
        old_status=old_status.value,
        new_status=new_status.value,
        description=(
            f"Trạng thái thay đổi từ {old_status.value} "
            f"sang {new_status.value}"
        ),
    )

    db.add(history)

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
    if task.status != TaskStatus.CANCELLED:
        try:
            assignment.status = AssignmentStatus(task.status.value)
        except ValueError:
            pass
    db.commit()
    db.refresh(assignment)
    return assignment


def get_task_progress(
    db: Session,
    task_id: int,
    user: User,
) -> TaskAssignment:
    task = _get_task(db, task_id)
    if user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ sinh viên được giao nhiệm vụ mới có thể xem tiến độ cá nhân.",
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
    return assignment


# Task Comment
def _assert_can_comment(db: Session, task: Task, user: User) -> None:
    if user.role == UserRole.ADMIN:
        return

    if user.role == UserRole.STUDENT:
        student_id = db.scalar(
            select(Student.id).where(Student.user_id == user.id)
        )

        is_member = student_id is not None and db.scalar(
            select(TeamMember.id).where(
                TeamMember.team_id == task.team_id,
                TeamMember.student_id == student_id,
            )
        )

        if is_member:
            return
    else:
        _assert_task_manager(db, task, user)
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bạn không có quyền bình luận nhiệm vụ này.",
    )


def create_task_comment(
    db: Session,
    task_id: int,
    data: TaskCommentCreate,
    user: User,
) -> TaskComment:
    task = _get_task(db, task_id)
    _assert_can_comment(db, task, user)

    comment = TaskComment(
        task_id=task.id,
        user_id=user.id,
        content=data.content,
    )

    db.add(comment)
    db.commit()
    db.refresh(comment)

    return comment


def get_task_comments(
    db: Session,
    task_id: int,
    user: User,
) -> list[TaskComment]:
    task = _get_task(db, task_id)
    _assert_can_comment(db, task, user)

    return list(
        db.scalars(
            select(TaskComment)
            .where(TaskComment.task_id == task.id)
            .order_by(TaskComment.created_at.asc(), TaskComment.id.asc())
        ).all()
    )
