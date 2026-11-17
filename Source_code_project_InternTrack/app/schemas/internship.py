
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.internship_period import PeriodStatus


class InternshipCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150, pattern=r".*\S.*")
    description: str | None = None
    start_date: date
    end_date: date
    report_deadline: datetime | None = None
    status: PeriodStatus = PeriodStatus.UPCOMING


class InternshipUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=150, pattern=r".*\S.*")
    description: str | None = None
    start_date: date
    end_date: date
    report_deadline: datetime | None = None


class InternshipStatusUpdate(BaseModel):
    status: PeriodStatus


class InternshipResponse(BaseModel):
    id: int
    name: str
    description: str | None
    start_date: date
    end_date: date
    report_deadline: datetime | None
    status: PeriodStatus
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
