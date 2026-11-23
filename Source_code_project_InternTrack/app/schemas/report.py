from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportCreate(BaseModel):
    student_id: int | None = Field(default=None, gt=0)
    team_id: int | None = Field(default=None, gt=0)
    period_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    report_type: str = Field(pattern="^(WEEKLY|FINAL)$")


class ReportReviewUpdate(BaseModel):
    status: str = Field(pattern="^(REVIEWING|REVISION_REQUIRED|APPROVED)$")
    content: str = Field(min_length=1, max_length=5000)


class ReportReviewResponse(BaseModel):
    id: int
    reviewer_id: int
    content: str
    status: str
    created_at: datetime


class ReportResponse(BaseModel):
    id: int
    student_id: int | None = None
    team_id: int | None = None
    period_id: int
    title: str
    report_type: str
    file_url: str | None = None
    status: str
    submitted_at: datetime | None = None
    created_at: datetime
    owner_name: str | None = None
    reviews: list[ReportReviewResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)