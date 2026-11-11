from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    task = relationship("Task", back_populates="comments")
    user = relationship("User")