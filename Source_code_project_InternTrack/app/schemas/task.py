from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.task import TaskPriority, TaskStatus, TaskType
from app.models.task_assignment import AssignmentStatus


class TaskCreate(BaseModel):
    team_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    task_type: TaskType
    priority: TaskPriority
    start_date: date
    deadline: datetime

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title must not be blank.")
        return value

    @model_validator(mode="after")
    def deadline_must_follow_start_date(self) -> "TaskCreate":
        if self.deadline.date() < self.start_date:
            raise ValueError("Deadline must not be before the start date.")
        return self


class TaskAssign(BaseModel):
    student_id: int = Field(gt=0)


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskProgressUpdate(BaseModel):
    progress: int = Field(strict=True, ge=0, le=100)


class TaskResponse(BaseModel):
    id: int
    team_id: int
    title: str
    description: str | None
    task_type: TaskType
    priority: TaskPriority
    status: TaskStatus
    start_date: date
    deadline: datetime
    created_by: int
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TaskAssignmentResponse(BaseModel):
    id: int
    task_id: int
    student_id: int
    assigned_by: int
    assigned_at: datetime
    progress: int
    status: AssignmentStatus

    model_config = ConfigDict(from_attributes=True)