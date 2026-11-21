from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DiaryReviewUpdate(BaseModel):
    status: str = Field(pattern="^(REVIEWED|REVISION_REQUIRED)$")
    content: str = Field(min_length=1, max_length=5000)


class DiaryResponse(BaseModel):
    id: int
    student_id: int
    task_id: int | None = None
    work_date: date
    work_content: str
    result: str | None = None
    difficulties: str | None = None
    lessons_learned: str | None = None
    status: str
    created_at: datetime
    student_name: str | None = None
    student_code: str | None = None

    model_config = ConfigDict(from_attributes=True)