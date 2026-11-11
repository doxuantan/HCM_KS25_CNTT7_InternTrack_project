from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class Lecturer(Base):
    __tablename__ = "lecturers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     unique=True, nullable=False)
    lecturer_code = Column(String(30), unique=True, nullable=False)
    department = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)

    user = relationship("User")