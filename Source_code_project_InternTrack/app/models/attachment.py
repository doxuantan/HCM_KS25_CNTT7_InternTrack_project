from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        # Tệp phải thuộc đúng một đối tượng: task, nhật ký hoặc báo cáo
        CheckConstraint(
            "(task_id IS NOT NULL) + (diary_id IS NOT NULL) + (report_id IS NOT NULL) = 1",
            name="ck_attachments_one_target",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    diary_id = Column(Integer, ForeignKey("internship_diaries.id"), nullable=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now())

    uploader = relationship("User", foreign_keys=[uploaded_by])
    task = relationship("Task")
    diary = relationship("InternshipDiary")
    report = relationship("Report")