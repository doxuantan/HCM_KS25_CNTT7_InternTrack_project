import enum

from sqlalchemy import Column, Date, DateTime, Enum, Integer, String, Text, func

from app.db.database import Base


class PeriodStatus(str, enum.Enum):
    UPCOMING = "UPCOMING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class InternshipPeriod(Base):
    __tablename__ = "internship_periods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    report_deadline = Column(DateTime, nullable=True)
    status = Column(Enum(PeriodStatus), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())