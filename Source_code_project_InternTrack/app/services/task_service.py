from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select, or_
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
    TaskUpdate,
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

    if user.role == UserRole.STUDENT:
        student_id = db.scalar(
            select(Student.id).where(Student.user_id == user.id)
        )
        if student_id is not None:
            is_team_leader = db.scalar(
                select(TeamMember.id).where(
                    TeamMember.team_id == task.team_id,
                    TeamMember.student_id == student_id,
                    TeamMember.is_leader.is_(True),
                )
            )
            if is_team_leader is not None:
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

    if user.role == UserRole.STUDENT:
        student_id = db.scalar(
            select(Student.id).where(Student.user_id == user.id)
        )
        is_team_leader = student_id is not None and db.scalar(
            select(TeamMember.id).where(
                TeamMember.team_id == team.id,
                TeamMember.student_id == student_id,
                TeamMember.is_leader.is_(True),
            )
        ) is not None
        if not is_team_leader:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ nhóm trưởng mới được tạo nhiệm vụ cho nhóm.",
            )
        if data.task_type.value != "TEAM":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Nhóm trưởng chỉ được tạo nhiệm vụ thuộc nhóm.",
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


def get_task(db: Session, task_id: int, user: User) -> Task:
    task = _get_task(db, task_id)
    if user.role == UserRole.ADMIN:
        return task
    if user.role == UserRole.SUPERVISOR:
        _assert_task_manager(db, task, user)
        return task
    if user.role == UserRole.STUDENT:
        student_id = db.scalar(
            select(Student.id).where(Student.user_id == user.id)
        )
        if student_id is not None:
            is_team_leader = db.scalar(
                select(TeamMember.id).where(
                    TeamMember.team_id == task.team_id,
                    TeamMember.student_id == student_id,
                    TeamMember.is_leader.is_(True),
                )
            )
            if is_team_leader is not None:
                return task
            assigned = db.scalar(
                select(TaskAssignment.id).where(
                    TaskAssignment.task_id == task.id,
                    TaskAssignment.student_id == student_id,
                )
            )
            if assigned is not None:
                return task
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bạn không có quyền xem nhiệm vụ này.",
    )


def update_task(db: Session, task_id: int, data: TaskUpdate, user: User) -> Task:
    task = _get_task(db, task_id)
    _assert_task_manager(db, task, user)
    update_data = data.model_dump(exclude_unset=True)

    if user.role == UserRole.STUDENT and "team_id" in update_data:
        if update_data["team_id"] != task.team_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nhóm trưởng không được chuyển nhiệm vụ sang nhóm khác.",
            )

    team_id = update_data.get("team_id", task.team_id)
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhóm.")
    if user.role == UserRole.SUPERVISOR:
        lecturer_id = db.scalar(
            select(Lecturer.id).where(Lecturer.user_id == user.id)
        )
        if lecturer_id != team.supervisor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Giảng viên không có quyền quản lý nhiệm vụ trong nhóm này.",
            )

    start_date = update_data.get("start_date", task.start_date)
    deadline = update_data.get("deadline", task.deadline)
    deadline = _local_naive_datetime(deadline)
    if deadline.date() < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Hạn hoàn thành phải cùng hoặc sau ngày bắt đầu.",
        )

    if "team_id" in update_data:
        for assignment in task.assignments:
            is_member = db.scalar(
                select(TeamMember.id).where(
                    TeamMember.team_id == team_id,
                    TeamMember.student_id == assignment.student_id,
                )
            )
            if is_member is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Người được giao phải là thành viên của nhóm mới.",
                )

    for field, value in update_data.items():
        if field == "deadline":
            value = deadline
        setattr(task, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể cập nhật nhiệm vụ do dữ liệu liên kết không hợp lệ.",
        ) from None
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int, user: User) -> None:
    task = _get_task(db, task_id)
    _assert_task_manager(db, task, user)
    db.delete(task)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể xóa nhiệm vụ vì còn dữ liệu liên kết.",
        ) from None


def list_tasks(
    db: Session,
    user: User,
    *,
    team: int | None = None,
    status: TaskStatus | None = None,
    assignee: int | None = None,
    priority = None,
    q: str | None = None,
    deadline_from: datetime | None = None,
    deadline_to: datetime | None = None,
    sort: str = "created_desc",
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
        leader_team_ids = db.scalars(
            select(TeamMember.team_id).where(
                TeamMember.student_id == student_id,
                TeamMember.is_leader.is_(True),
            )
        ).all()
        if leader_team_ids:
            statement = statement.where(Task.team_id.in_(leader_team_ids))
            if assignee is not None:
                statement = statement.where(
                    select(TaskAssignment.id)
                    .where(
                        TaskAssignment.task_id == Task.id,
                        TaskAssignment.student_id == assignee,
                    )
                    .exists()
                )
                assignee = None
        else:
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
    if priority is not None:
        statement = statement.where(Task.priority == priority)
    if q and q.strip():
        keyword = f"%{q.strip()}%"
        statement = statement.where(
            or_(Task.title.ilike(keyword), Task.description.ilike(keyword))
        )
    if deadline_from is not None:
        statement = statement.where(Task.deadline >= deadline_from)
    if deadline_to is not None:
        statement = statement.where(Task.deadline <= deadline_to)

    count_statement = select(func.count()).select_from(
        statement.with_only_columns(Task.id).order_by(None).subquery()
    )
    total = db.scalar(count_statement) or 0
    sort_options = {
        "title_asc": Task.title.asc(),
        "title_desc": Task.title.desc(),
        "created_asc": Task.created_at.asc(),
        "created_desc": Task.created_at.desc(),
        "deadline_asc": Task.deadline.asc(),
        "deadline_desc": Task.deadline.desc(),
    }
    tasks = db.scalars(
        statement.order_by(sort_options[sort], Task.id.desc()).offset((page - 1) * limit).limit(limit)
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
    elif data.status == TaskReviewStatus.REJECTED:
        new_status = TaskStatus.CANCELLED
        for assignment in task.assignments:
            assignment.status = AssignmentStatus.IN_PROGRESS
        description = "Task review rejected."
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
            else (
                "Đã từ chối nhiệm vụ."
                if data.status == TaskReviewStatus.REJECTED
                else "Đã yêu cầu sinh viên sửa lại nhiệm vụ."
            )
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

        allowed_for_student = {
            TaskStatus.TODO: {TaskStatus.IN_PROGRESS},
            TaskStatus.IN_PROGRESS: {TaskStatus.TODO, TaskStatus.REVIEW},
            TaskStatus.REVIEW: {TaskStatus.IN_PROGRESS},
        }

        if new_status not in allowed_for_student.get(old_status, set()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Sinh viên chỉ được chuyển task trong các cột "
                       "TODO, In Progress và trạng thái REVIEW.",
            )

    else:
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
        try:
            assignment.status = AssignmentStatus(new_status.value)
        except ValueError:
            pass

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
