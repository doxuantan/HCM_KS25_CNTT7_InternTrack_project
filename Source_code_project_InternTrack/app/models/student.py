from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     unique=True, nullable=False)
    student_code = Column(String(30), unique=True, nullable=False)
    class_name = Column(String(100), nullable=True)
    major = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)

    # Quan hệ 1-1 với users
    user = relationship("User", back_populates="student")