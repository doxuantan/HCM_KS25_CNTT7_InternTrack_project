from datetime import date, datetime

from pydantic import BaseModel


class UpcomingTaskResponse(BaseModel):
    id: int
    team_id: int
    title: str
    status: str
    priority: str
    deadline: datetime
    start_date: date | None = None
    description: str | None = None
    is_overdue: bool = False


class ProgressStatsResponse(BaseModel):
    scope: str
    progress: float
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    todo_tasks: int
    not_started_tasks: int
    overdue_tasks: int
    upcoming_tasks: list[UpcomingTaskResponse]


class MemberProgressResponse(ProgressStatsResponse):
    student_id: int
    student_name: str | None = None
    student_code: str | None = None


class TeamMemberProgressResponse(BaseModel):
    student_id: int
    student_name: str | None = None
    student_code: str | None = None
    progress: float
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    todo_tasks: int
    overdue_tasks: int


class TeamProgressResponse(ProgressStatsResponse):
    team_id: int
    team_name: str
    members: list[TeamMemberProgressResponse]