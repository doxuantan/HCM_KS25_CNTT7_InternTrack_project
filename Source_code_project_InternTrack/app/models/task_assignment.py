import enum

from sqlalchemy import (CheckConstraint, Column, DateTime, Enum, ForeignKey,
                        Index, Integer, UniqueConstraint, func)
from sqlalchemy.orm import relationship

from app.db.database import Base


class AssignmentStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    DONE = "DONE"


class TaskAssignment(Base):
    __tablename__ = "task_assignments"
    __table_args__ = (
        UniqueConstraint("task_id", "student_id", name="uq_task_assignments_task_student"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_task_assignments_progress"),
        Index("ix_task_assignments_student_status", "student_id", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime, nullable=False, server_default=func.now())
    progress = Column(Integer, nullable=False, default=0, server_default="0")
    status = Column(Enum(AssignmentStatus), nullable=False, default=AssignmentStatus.TODO)

    task = relationship("Task", back_populates="assignments")
    student = relationship("Student")
    assigner = relationship("User", foreign_keys=[assigned_by])