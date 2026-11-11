from sqlalchemy import (Column, ForeignKey, Integer, Numeric, Text,
                        UniqueConstraint)
from sqlalchemy.orm import relationship

from app.db.database import Base


class EvaluationDetail(Base):
    __tablename__ = "evaluation_details"
    __table_args__ = (
        # Mỗi tiêu chí chỉ xuất hiện một lần trong cùng một phiếu đánh giá
        UniqueConstraint("evaluation_id", "criteria_id",
                         name="uq_evaluation_details_evaluation_criteria"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id", ondelete="CASCADE"),
                           nullable=False)
    criteria_id = Column(Integer, ForeignKey("evaluation_criteria.id"), nullable=False)
    score = Column(Numeric(5, 2), nullable=False)
    comment = Column(Text, nullable=True)

    evaluation = relationship("Evaluation", back_populates="details")
    criteria = relationship("EvaluationCriteria")