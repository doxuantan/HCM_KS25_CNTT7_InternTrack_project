import enum

from sqlalchemy import (CheckConstraint, Column, DateTime, Enum, ForeignKey,
                        Integer, String, Text, func)
from sqlalchemy.orm import relationship

from app.db.database import Base


class ReportType(str, enum.Enum):
    WEEKLY = "WEEKLY"  # Báo cáo tuần
    FINAL = "FINAL"    # Báo cáo cuối kỳ


class ReportStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    REVIEWING = "REVIEWING"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    APPROVED = "APPROVED"


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        # Một báo cáo chỉ thuộc một đối tượng: cá nhân HOẶC nhóm
        CheckConstraint("(student_id IS NULL) <> (team_id IS NULL)",
                        name="ck_reports_one_target"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    period_id = Column(Integer, ForeignKey("internship_periods.id"), nullable=False)
    title = Column(String(200), nullable=False)
    report_type = Column(Enum(ReportType), nullable=False)
    file_url = Column(String(500), nullable=True)
    status = Column(Enum(ReportStatus), nullable=False, default=ReportStatus.DRAFT)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    student = relationship("Student")
    team = relationship("Team")
    period = relationship("InternshipPeriod")