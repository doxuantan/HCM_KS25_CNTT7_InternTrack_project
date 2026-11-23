from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DiaryCreate(BaseModel):
    task_id: int | None = Field(default=None, gt=0)
    work_date: date
    work_content: str = Field(min_length=1, max_length=10000)
    result: str | None = Field(default=None, max_length=10000)
    difficulties: str | None = Field(default=None, max_length=10000)
    lessons_learned: str | None = Field(default=None, max_length=10000)


class DiaryReviewUpdate(BaseModel):
    status: str = Field(pattern="^(REVIEWED|REVISION_REQUIRED)$")
    content: str = Field(min_length=1, max_length=5000)


class DiaryReviewResponse(BaseModel):
    id: int
    reviewer_id: int
    content: str
    status: str
    created_at: datetime


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
    reviews: list[DiaryReviewResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)