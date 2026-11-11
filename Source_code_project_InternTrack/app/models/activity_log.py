from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User")