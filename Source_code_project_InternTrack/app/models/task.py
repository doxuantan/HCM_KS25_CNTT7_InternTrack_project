import enum
from datetime import datetime

from sqlalchemy import (CheckConstraint, Column, Date, DateTime, Enum,
                        ForeignKey, Index, Integer, String, Text, func)
from sqlalchemy.orm import relationship

from app.db.database import Base


class TaskType(str, enum.Enum):
    TEAM = "TEAM"
    PERSONAL = "PERSONAL"


class TaskPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TaskStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("DATE(deadline) >= start_date", name="ck_tasks_deadline_after_start"),
        Index("ix_tasks_team_status_deadline", "team_id", "status", "deadline"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(Enum(TaskType), nullable=False)
    priority = Column(Enum(TaskPriority), nullable=False)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.TODO)
    start_date = Column(Date, nullable=False)
    deadline = Column(DateTime, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    # Quan hệ sang model có sẵn
    team = relationship("Team")
    creator = relationship("User", foreign_keys=[created_by])

    # Quan hệ sang các bảng con
    assignments = relationship("TaskAssignment", back_populates="task",
                               cascade="all, delete-orphan", passive_deletes=True)
    comments = relationship("TaskComment", back_populates="task",
                            cascade="all, delete-orphan", passive_deletes=True,
                            order_by="TaskComment.created_at")
    history = relationship("TaskHistory", back_populates="task",
                           cascade="all, delete-orphan", passive_deletes=True,
                           order_by="TaskHistory.created_at")

    @property
    def is_overdue(self) -> bool:
        # Quá hạn: deadline đã qua và chưa DONE/CANCELLED (không có trạng thái OVERDUE riêng)
        return (self.deadline is not None
                and self.deadline < datetime.now()
                and self.status not in (TaskStatus.DONE, TaskStatus.CANCELLED))