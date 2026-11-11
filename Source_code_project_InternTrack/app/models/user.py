import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, func, true
from sqlalchemy.orm import relationship

from app.db.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"
    STUDENT = "STUDENT"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    avatar = Column(String(500), nullable=True)
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    # Quan hệ 1-1 với students
    student = relationship("Student", back_populates="user", uselist=False)