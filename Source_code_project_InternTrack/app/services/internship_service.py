
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.internship_period import InternshipPeriod, PeriodStatus
from app.models.team import Team
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


def get_all_internships(db: Session):
    statement = select(InternshipPeriod).order_by(
        InternshipPeriod.id.desc()
    )
    return db.scalars(statement).all()


def get_internship_by_id(db: Session, internship_id: int):
    internship = db.get(InternshipPeriod, internship_id)

    if not internship:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy kỳ thực tập."
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
