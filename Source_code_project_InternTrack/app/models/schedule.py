from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    team = relationship("Team")
    creator = relationship("User", foreign_keys=[created_by])