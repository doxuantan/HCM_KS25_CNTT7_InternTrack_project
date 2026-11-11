import enum

from sqlalchemy import (Column, Date, DateTime, Enum, ForeignKey, Index,
                        Integer, Text, func)
from sqlalchemy.orm import relationship

from app.db.database import Base


class DiaryStatus(str, enum.Enum):
    DRAFT = "DRAFT"          # Bản nháp
    SUBMITTED = "SUBMITTED"  # Đã nộp
    REVIEWED = "REVIEWED"    # Đã nhận xét


class InternshipDiary(Base):
    __tablename__ = "internship_diaries"
    __table_args__ = (
        Index("ix_internship_diaries_student_date", "student_id", "work_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    # Task liên quan, có thể NULL; nếu task bị xóa thì chỉ bỏ liên kết, giữ lại nhật ký
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    work_date = Column(Date, nullable=False)
    work_content = Column(Text, nullable=False)
    result = Column(Text, nullable=True)
    difficulties = Column(Text, nullable=True)
    lessons_learned = Column(Text, nullable=True)
    status = Column(Enum(DiaryStatus), nullable=False, default=DiaryStatus.DRAFT)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    student = relationship("Student")
    task = relationship("Task")