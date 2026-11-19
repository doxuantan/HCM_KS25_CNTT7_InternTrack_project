from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lecturer import Lecturer
from app.models.schedule import Schedule
from app.models.student import Student
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from app.services.notification_service import notify_schedule_created


def _lecturer_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Lecturer.id).where(Lecturer.user_id == user.id))


def _student_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Student.id).where(Student.user_id == user.id))


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


def _assert_team_access(db: Session, team: Team, user: User, *, manage: bool) -> None:
    if user.role == UserRole.ADMIN:
        return

    if user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        if lecturer_id is not None and team.supervisor_id == lecturer_id:
            return
    elif not manage and user.role == UserRole.STUDENT:
        student_id = _student_id(db, user)
        if student_id is not None:
            member = db.scalar(
                select(TeamMember.id).where(
                    TeamMember.team_id == team.id,
                    TeamMember.student_id == student_id,
                )
            )
            if member is not None:
                return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bạn không có quyền truy cập lịch của nhóm này.",
    )


def create_schedule(db: Session, data: ScheduleCreate, user: User) -> Schedule:
    team = db.get(Team, data.team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhóm.")

    _assert_team_access(db, team, user, manage=True)
    start_time = _normalize_datetime(data.start_time)
    end_time = _normalize_datetime(data.end_time)
    if end_time <= start_time:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Thời gian kết thúc phải sau thời gian bắt đầu.")

    schedule = Schedule(
        team_id=data.team_id,
        created_by=user.id,
        title=data.title,
        description=data.description,
        location=data.location,
        start_time=start_time,
        end_time=end_time,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    notify_schedule_created(
        db,
        team_id=schedule.team_id,
        title=schedule.title,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
    )
    return schedule


def get_schedules(db: Session, user: User) -> list[Schedule]:
    statement = select(Schedule)
    if user.role == UserRole.ADMIN:
        pass
    elif user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        if lecturer_id is None:
            return []
        statement = statement.join(Team, Team.id == Schedule.team_id).where(
            Team.supervisor_id == lecturer_id
        )
    elif user.role == UserRole.STUDENT:
        student_id = _student_id(db, user)
        if student_id is None:
            return []
        statement = statement.join(TeamMember, TeamMember.team_id == Schedule.team_id).where(
            TeamMember.student_id == student_id
        )
    else:
        return []
    return list(db.scalars(statement.order_by(Schedule.start_time.asc(), Schedule.id.asc())).unique().all())


def get_schedule(db: Session, schedule_id: int, user: User) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch.")
    team = db.get(Team, schedule.team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhóm của lịch.")
    _assert_team_access(db, team, user, manage=False)
    return schedule


def update_schedule(db: Session, schedule_id: int, data: ScheduleUpdate, user: User) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch.")

    team_id = data.team_id if data.team_id is not None else schedule.team_id
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhóm.")
    _assert_team_access(db, team, user, manage=True)

    start_time = _normalize_datetime(data.start_time) if data.start_time is not None else schedule.start_time
    end_time = _normalize_datetime(data.end_time) if data.end_time is not None else schedule.end_time
    if end_time <= start_time:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Thời gian kết thúc phải sau thời gian bắt đầu.")

    if data.team_id is not None:
        schedule.team_id = data.team_id
    if data.title is not None:
        schedule.title = data.title
    if "description" in data.model_fields_set:
        schedule.description = data.description
    if "location" in data.model_fields_set:
        schedule.location = data.location
    schedule.start_time = start_time
    schedule.end_time = end_time

    db.commit()
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule_id: int, user: User) -> None:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch.")
    team = db.get(Team, schedule.team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhóm của lịch.")
    _assert_team_access(db, team, user, manage=True)
    db.delete(schedule)
    db.commit()