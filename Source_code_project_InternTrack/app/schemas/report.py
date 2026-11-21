from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportReviewUpdate(BaseModel):
    status: str = Field(pattern="^(REVIEWING|REVISION_REQUIRED|APPROVED)$")
    content: str = Field(min_length=1, max_length=5000)


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

    model_config = ConfigDict(from_attributes=True)