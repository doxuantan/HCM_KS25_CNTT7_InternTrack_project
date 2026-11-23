<<<<<<< HEAD
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
    supervisor_name: str | None = None
    supervisor_code: str | None = None
=======
from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.internship_period import PeriodStatus
from app.models.team import TeamStatus


class TeamPeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    start_date: date
    end_date: date
    status: PeriodStatus


class TeamSupervisorResponse(BaseModel):
    full_name: str
    email: str


class TeamStudentResponse(BaseModel):
    student_code: str
    full_name: str
    email: str
    is_leader: bool


class StudentTeamResponse(BaseModel):
    id: int
>>>>>>> c0d965d4a2cdd96a21dfeed751592df2c4323a18
    team_name: str
    team_code: str
    description: str | None
    status: TeamStatus
<<<<<<< HEAD
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamMemberAdd(BaseModel):
    student_id: int = Field(gt=0)


class TeamMemberResponse(BaseModel):
    id: int
    team_id: int
    student_id: int
    is_leader: bool
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamLeaderUpdate(BaseModel):
    student_id: int | None = Field(default=None, gt=0)
    leader_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_student(self):
        if self.student_id is None and self.leader_id is None:
            raise ValueError("student_id or leader_id is required.")
        if self.student_id is not None and self.leader_id is not None:
            if self.student_id != self.leader_id:
                raise ValueError("student_id and leader_id must match.")
        return self


class TeamSupervisorUpdate(BaseModel):
    supervisor_id: int | None = Field(default=None, gt=0)
    lecturer_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_supervisor(self):
        if self.supervisor_id is None and self.lecturer_id is None:
            raise ValueError("supervisor_id or lecturer_id is required.")
        if self.supervisor_id is not None and self.lecturer_id is not None:
            if self.supervisor_id != self.lecturer_id:
                raise ValueError("supervisor_id and lecturer_id must match.")
        return self


class TeamMemberDetail(BaseModel):
    id: int
    team_id: int
    student_id: int
    is_leader: bool
    joined_at: datetime
    student_name: str | None = None
    student_code: str | None = None

    model_config = ConfigDict(from_attributes=True)
=======
    period: TeamPeriodResponse
    supervisor: TeamSupervisorResponse
    members: list[TeamStudentResponse]
>>>>>>> c0d965d4a2cdd96a21dfeed751592df2c4323a18
