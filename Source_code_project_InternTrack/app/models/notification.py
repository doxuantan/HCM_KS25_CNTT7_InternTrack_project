from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Index, Integer,
                        String, Text, false, func)
from sqlalchemy.orm import relationship

from app.db.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read_created", "user_id", "is_read", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    notification_type = Column(String(50), nullable=True)
    is_read = Column(Boolean, nullable=False, default=False, server_default=false())
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User")