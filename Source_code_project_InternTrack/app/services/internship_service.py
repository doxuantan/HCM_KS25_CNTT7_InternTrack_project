
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.internship_period import InternshipPeriod, PeriodStatus
from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole
from app.schemas.internship import (
    InternshipCreate,
    InternshipUpdate,
)


def validate_dates(start_date: date, end_date: date):
    if end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu."
        )


def get_all_internships(db: Session, user: User):
    if user.role == UserRole.ADMIN:
        statement = select(InternshipPeriod)
    elif user.role == UserRole.SUPERVISOR:
        lecturer_id = db.scalar(select(Lecturer.id).where(Lecturer.user_id == user.id))
        if lecturer_id is None:
            return []
        statement = (
            select(InternshipPeriod)
            .join(Team, Team.period_id == InternshipPeriod.id)
            .where(Team.supervisor_id == lecturer_id)
        )
    elif user.role == UserRole.STUDENT:
        student_id = db.scalar(select(Student.id).where(Student.user_id == user.id))
        if student_id is None:
            return []
        statement = (
            select(InternshipPeriod)
            .join(Team, Team.period_id == InternshipPeriod.id)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(TeamMember.student_id == student_id)
        )
    else:
        return []
    return db.scalars(statement.distinct().order_by(InternshipPeriod.id.desc())).all()


def get_internship_by_id(db: Session, internship_id: int, user: User | None = None):
    internship = db.get(InternshipPeriod, internship_id)

    if not internship:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy kỳ thực tập."
        )

    if user is not None and user.role != UserRole.ADMIN:
        if user.role == UserRole.SUPERVISOR:
            lecturer_id = db.scalar(select(Lecturer.id).where(Lecturer.user_id == user.id))
            allowed = lecturer_id is not None and db.scalar(
                select(Team.id).where(
                    Team.period_id == internship_id,
                    Team.supervisor_id == lecturer_id,
                )
            ) is not None
        elif user.role == UserRole.STUDENT:
            student_id = db.scalar(select(Student.id).where(Student.user_id == user.id))
            allowed = student_id is not None and db.scalar(
                select(TeamMember.id)
                .join(Team, TeamMember.team_id == Team.id)
                .where(
                    Team.period_id == internship_id,
                    TeamMember.student_id == student_id,
                )
            ) is not None
        else:
            allowed = False
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail="Bạn không có quyền truy cập kỳ thực tập ngoài phạm vi.",
            )

    return internship


def create_internship(db: Session, data: InternshipCreate):
    validate_dates(data.start_date, data.end_date)

    internship = InternshipPeriod(**data.model_dump())

    db.add(internship)
    db.commit()
    db.refresh(internship)

    return internship


def update_internship(
    db: Session,
    internship_id: int,
    data: InternshipUpdate
):
    internship = get_internship_by_id(db, internship_id)

    validate_dates(data.start_date, data.end_date)

    update_data = data.model_dump()

    for key, value in update_data.items():
        setattr(internship, key, value)

    db.commit()
    db.refresh(internship)

    return internship


def update_internship_status(
    db: Session,
    internship_id: int,
    status: PeriodStatus
):
    internship = get_internship_by_id(db, internship_id)

    internship.status = status

    db.commit()
    db.refresh(internship)

    return internship


def delete_internship(db: Session, internship_id: int):
    internship = get_internship_by_id(db, internship_id)

    # Không xóa kỳ thực tập đang có nhóm liên kết.
    team = db.scalar(
        select(Team).where(Team.period_id == internship_id)
    )

    if team:
        raise HTTPException(
            status_code=400,
            detail="Không thể xóa kỳ thực tập đang có nhóm."
        )

    db.delete(internship)
    db.commit()

    return True
