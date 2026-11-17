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
    team_name: str
    team_code: str
    description: str | None
    status: TeamStatus
    period: TeamPeriodResponse
    supervisor: TeamSupervisorResponse
    members: list[TeamStudentResponse]