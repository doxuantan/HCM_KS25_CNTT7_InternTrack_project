import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class ReportReviewStatus(str, enum.Enum):
    REVIEWING = "REVIEWING"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    APPROVED = "APPROVED"


class ReportReview(Base):
    __tablename__ = "report_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(Enum(ReportReviewStatus), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    report = relationship("Report")
    reviewer = relationship("User", foreign_keys=[reviewer_id])