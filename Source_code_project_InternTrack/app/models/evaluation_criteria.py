from sqlalchemy import Boolean, Column, Integer, Numeric, String, Text, true

from app.db.database import Base


class EvaluationCriteria(Base):
    __tablename__ = "evaluation_criteria"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    weight = Column(Numeric(5, 2), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())