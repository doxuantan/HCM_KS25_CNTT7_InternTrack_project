from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.team import TeamStatus


class TeamCreate(BaseModel):
    period_id: int = Field(gt=0)
    supervisor_id: int | None = Field(default=None, gt=0)
    team_name: str = Field(min_length=1, max_length=100)
    team_code: str = Field(min_length=1, max_length=30)
    description: str | None = None
    status: TeamStatus = TeamStatus.ACTIVE

    model_config = ConfigDict(str_strip_whitespace=True)


class TeamUpdate(BaseModel):
    period_id: int | None = Field(default=None, gt=0)
    supervisor_id: int | None = Field(default=None, gt=0)
    team_name: str | None = Field(default=None, min_length=1, max_length=100)
    team_code: str | None = Field(default=None, min_length=1, max_length=30)
    description: str | None = None
    status: TeamStatus | None = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")

        nullable_fields = {"description"}
        for field in self.model_fields_set - nullable_fields:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        return self


class TeamResponse(BaseModel):
    id: int
    period_id: int
    supervisor_id: int
    team_name: str
    team_code: str
    description: str | None
    status: TeamStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)