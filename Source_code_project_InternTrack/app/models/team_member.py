from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer,
                        UniqueConstraint, false, func)
from sqlalchemy.orm import relationship

from app.db.database import Base


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        # Một sinh viên không xuất hiện hai lần trong cùng một nhóm
        UniqueConstraint("team_id", "student_id", name="uq_team_members_team_student"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    is_leader = Column(Boolean, nullable=False, default=False, server_default=false())
    joined_at = Column(DateTime, nullable=False, server_default=func.now())

    team = relationship("Team", back_populates="members")
    members = relationship("TeamMember", back_populates="team",
                           cascade="all, delete-orphan", passive_deletes=True)
    student = relationship("Student")