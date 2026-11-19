from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScheduleCreate(BaseModel):
    team_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    location: str | None = Field(default=None, max_length=255)
    start_time: datetime
    end_time: datetime

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class ScheduleUpdate(BaseModel):
    team_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    location: str | None = Field(default=None, max_length=255)
    start_time: datetime | None = None
    end_time: datetime | None = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title cannot be null.")
        if "team_id" in self.model_fields_set and self.team_id is None:
            raise ValueError("team_id cannot be null.")

        start_time = self.start_time
        end_time = self.end_time
        if start_time is not None and end_time is not None and end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        return self


class ScheduleResponse(BaseModel):
    id: int
    team_id: int
    created_by: int
    title: str
    description: str | None
    location: str | None
    start_time: datetime
    end_time: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)