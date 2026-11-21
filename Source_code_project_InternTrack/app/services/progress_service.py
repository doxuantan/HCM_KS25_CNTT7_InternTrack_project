from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.task import Task, TaskStatus
from app.models.task_assignment import TaskAssignment
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole


def _lecturer_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Lecturer.id).where(Lecturer.user_id == user.id))


def _student_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Student.id).where(Student.user_id == user.id))


def _local_naive_datetime(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


def _is_overdue(task: Task, now: datetime) -> bool:
    if task.status in (TaskStatus.DONE, TaskStatus.CANCELLED):
        return False
    return _local_naive_datetime(task.deadline) < now


def _percentage(completed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(completed * 100.0 / total, 2)


def _upcoming_tasks(tasks: list[Task], now: datetime) -> list[dict]:
    upcoming = [
        task for task in tasks
        if task.status not in (TaskStatus.DONE, TaskStatus.CANCELLED)
        and _local_naive_datetime(task.deadline) >= now
    ]
    upcoming.sort(key=lambda task: _local_naive_datetime(task.deadline))
    return [
        {
            "id": task.id,
            "team_id": task.team_id,
            "title": task.title,
            "status": task.status.value,
            "priority": task.priority.value,
            "deadline": _local_naive_datetime(task.deadline),
            "start_date": task.start_date,
            "description": task.description,
            "is_overdue": False,
        }
        for task in upcoming[:10]
    ]


def _task_stats(tasks: list[Task], now: datetime) -> dict:
    completed = sum(task.status == TaskStatus.DONE for task in tasks)
    in_progress = sum(task.status in (TaskStatus.IN_PROGRESS, TaskStatus.REVIEW) for task in tasks)
    todo = sum(task.status == TaskStatus.TODO for task in tasks)
    overdue = sum(_is_overdue(task, now) for task in tasks)
    total = len(tasks)
    return {
        "progress": _percentage(completed, total),
        "total_tasks": total,
        "completed_tasks": completed,
        "in_progress_tasks": in_progress,
        "todo_tasks": todo,
        "not_started_tasks": todo,
        "overdue_tasks": overdue,
    }


def _valid_team_tasks(db: Session, team_id: int) -> list[Task]:
    tasks = db.scalars(select(Task).where(Task.team_id == team_id)).all()
    return [
        task for task in tasks
        if task.status != TaskStatus.CANCELLED
        and db.scalar(
            select(TaskAssignment.id).where(TaskAssignment.task_id == task.id).limit(1)
        ) is not None
    ]


def _valid_personal_tasks(db: Session, student_id: int) -> list[Task]:
    return db.scalars(
        select(Task)
        .join(TaskAssignment, TaskAssignment.task_id == Task.id)
        .where(
            TaskAssignment.student_id == student_id,
            Task.status != TaskStatus.CANCELLED,
        )
    ).unique().all()


def _valid_personal_team_tasks(db: Session, team_id: int, student_id: int) -> list[Task]:
    return db.scalars(
        select(Task)
        .join(TaskAssignment, TaskAssignment.task_id == Task.id)
        .where(
            Task.team_id == team_id,
            TaskAssignment.student_id == student_id,
            Task.status != TaskStatus.CANCELLED,
        )
    ).unique().all()


def _student_name_and_code(db: Session, student_id: int) -> tuple[str | None, str | None]:
    student = db.get(Student, student_id)
    if student is None:
        return None, None
    user = db.get(User, student.user_id)
    return (user.full_name if user else None), student.student_code


def _assert_team_access(db: Session, team_id: int, user: User) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhóm.")

    if user.role == UserRole.ADMIN:
        return team
    if user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        if lecturer_id == team.supervisor_id:
            return team
    if user.role == UserRole.STUDENT:
        student_id = _student_id(db, user)
        membership = db.scalar(
            select(TeamMember.id).where(
                TeamMember.team_id == team_id,
                TeamMember.student_id == student_id,
                TeamMember.is_leader.is_(True),
            )
        )
        if membership is not None:
            return team
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Chỉ quản trị viên, người hướng dẫn hoặc nhóm trưởng được xem tiến độ nhóm.",
    )


def get_my_progress(db: Session, user: User) -> dict:
    if user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ sinh viên có thể xem tiến độ cá nhân của mình.",
        )
    student_id = _student_id(db, user)
    if student_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tài khoản chưa được liên kết với hồ sơ sinh viên.",
        )
    return get_member_progress(db, student_id, user)


def get_team_progress(db: Session, team_id: int, user: User) -> dict:
    team = _assert_team_access(db, team_id, user)
    now = datetime.now()
    tasks = _valid_team_tasks(db, team_id)
    data = {"scope": "team", "team_id": team.id, "team_name": team.team_name}
    data.update(_task_stats(tasks, now))
    data["upcoming_tasks"] = _upcoming_tasks(tasks, now)

    members = db.scalars(
        select(TeamMember).where(TeamMember.team_id == team_id).order_by(TeamMember.id)
    ).all()
    member_rows = []
    for membership in members:
        member_tasks = _valid_personal_team_tasks(db, team_id, membership.student_id)
        member_stats = _task_stats(member_tasks, now)
        name, code = _student_name_and_code(db, membership.student_id)
        member_rows.append({
            "student_id": membership.student_id,
            "student_name": name,
            "student_code": code,
            "progress": member_stats["progress"],
            "total_tasks": member_stats["total_tasks"],
            "completed_tasks": member_stats["completed_tasks"],
            "in_progress_tasks": member_stats["in_progress_tasks"],
            "todo_tasks": member_stats["todo_tasks"],
            "overdue_tasks": member_stats["overdue_tasks"],
        })
    data["members"] = member_rows
    return data


def get_member_progress(db: Session, student_id: int, user: User) -> dict:
    resolved = db.get(Student, student_id)
    if resolved is None:
        resolved = db.scalar(select(Student).where(Student.user_id == student_id))
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sinh viên.",
        )
    student_id = resolved.id

    if user.role == UserRole.STUDENT:
        own_student_id = _student_id(db, user)
        if own_student_id != student_id:
            leader_team_ids = set(db.scalars(
                select(TeamMember.team_id).where(
                    TeamMember.student_id == own_student_id,
                    TeamMember.is_leader.is_(True),
                )
            ).all())
            target_team_ids = set(db.scalars(
                select(TeamMember.team_id).where(
                    TeamMember.student_id == student_id,
                )
            ).all())
            if leader_team_ids.isdisjoint(target_team_ids):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền xem tiến độ của sinh viên này.",
                )
    elif user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        allowed = db.scalar(
            select(TeamMember.id)
            .join(Team, Team.id == TeamMember.team_id)
            .where(
                TeamMember.student_id == student_id,
                Team.supervisor_id == lecturer_id,
            )
            .limit(1)
        )
        if allowed is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xem tiến độ thành viên ngoài phạm vi.",
            )
    elif user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập.")

    now = datetime.now()
    tasks = _valid_personal_tasks(db, student_id)
    name, code = _student_name_and_code(db, student_id)
    data = {
        "scope": "member",
        "student_id": student_id,
        "student_name": name,
        "student_code": code,
    }
    data.update(_task_stats(tasks, now))
    data["upcoming_tasks"] = _upcoming_tasks(tasks, now)
    return data


def get_progress_overview(db: Session, user: User) -> dict:
    now = datetime.now()
    valid_tasks: list[Task]

    if user.role == UserRole.ADMIN:
        valid_tasks = [
            task for task in db.scalars(select(Task)).all()
            if task.status != TaskStatus.CANCELLED
            and db.scalar(
                select(TaskAssignment.id).where(TaskAssignment.task_id == task.id).limit(1)
            ) is not None
        ]
    elif user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        team_ids = db.scalars(
            select(Team.id).where(Team.supervisor_id == lecturer_id)
        ).all()
        valid_tasks = []
        for team_id in team_ids:
            valid_tasks.extend(_valid_team_tasks(db, team_id))
    elif user.role == UserRole.STUDENT:
        student_id = _student_id(db, user)
        if student_id is None:
            valid_tasks = []
        else:
            leader_team_ids = db.scalars(
                select(TeamMember.team_id).where(
                    TeamMember.student_id == student_id,
                    TeamMember.is_leader.is_(True),
                )
            ).all()
            if leader_team_ids:
                valid_tasks = []
                for team_id in leader_team_ids:
                    valid_tasks.extend(_valid_team_tasks(db, team_id))
            else:
                valid_tasks = _valid_personal_tasks(db, student_id)
    else:
        valid_tasks = []

    unique_tasks = {task.id: task for task in valid_tasks}
    tasks = list(unique_tasks.values())
    data = {"scope": "overview"}
    data.update(_task_stats(tasks, now))
    data["upcoming_tasks"] = _upcoming_tasks(tasks, now)
    return data