from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, ForeignKey,
                        Index, Integer, Numeric, Text, false, func)
from sqlalchemy.orm import relationship

from app.db.database import Base


class Evaluation(Base):
    __tablename__ = "evaluations"
    __table_args__ = (
        # Mỗi phiếu đánh giá phải xác định đúng một đối tượng: sinh viên HOẶC nhóm
        CheckConstraint("(student_id IS NULL) <> (team_id IS NULL)",
                        name="ck_evaluations_one_target"),
        Index("ix_evaluations_student_period", "student_id", "period_id"),
        Index("ix_evaluations_team_period", "team_id", "period_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    evaluator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    period_id = Column(Integer, ForeignKey("internship_periods.id"), nullable=False)
    total_score = Column(Numeric(5, 2), nullable=True)
    comment = Column(Text, nullable=True)
    is_published = Column(Boolean, nullable=False, default=False, server_default=false())
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    student = relationship("Student")
    team = relationship("Team")
    evaluator = relationship("User", foreign_keys=[evaluator_id])
    period = relationship("InternshipPeriod")