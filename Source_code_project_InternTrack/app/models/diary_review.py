import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class DiaryReviewStatus(str, enum.Enum):
    REVIEWED = "REVIEWED"
    REVISION_REQUIRED = "REVISION_REQUIRED"


class DiaryReview(Base):
    __tablename__ = "diary_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    diary_id = Column(Integer, ForeignKey("internship_diaries.id", ondelete="CASCADE"),
                      nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(Enum(DiaryReviewStatus), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    diary = relationship("InternshipDiary")
    reviewer = relationship("User", foreign_keys=[reviewer_id])