from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class TaskHistory(Base):
    __tablename__ = "task_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    old_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    task = relationship("Task", back_populates="history")
    user = relationship("User")