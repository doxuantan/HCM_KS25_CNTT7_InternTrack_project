import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class TeamStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    COMPLETED = "COMPLETED"


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    period_id = Column(Integer, ForeignKey("internship_periods.id"), nullable=False)
    supervisor_id = Column(Integer, ForeignKey("lecturers.id"), nullable=False)
    team_name = Column(String(100), nullable=False)
    team_code = Column(String(30), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TeamStatus), nullable=False, default=TeamStatus.ACTIVE)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    period = relationship("InternshipPeriod")
    supervisor = relationship("Lecturer")
    members = relationship(
        "TeamMember",
        back_populates="team",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )