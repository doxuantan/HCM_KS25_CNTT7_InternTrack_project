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

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("deadline")
    @classmethod
    def normalize_deadline_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone().replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def validate_deadline_date(self):
        if self.deadline.date() < self.start_date:
            raise ValueError("Deadline must be on or after the task start date.")
        return self


class TaskAssign(BaseModel):
    student_id: int = Field(gt=0)


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskProgressUpdate(BaseModel):
    progress: int = Field(ge=0, le=100)


class TaskAssignmentResponse(BaseModel):
    id: int
    task_id: int
    student_id: int
    assigned_by: int
    assigned_at: datetime
    progress: int
    status: AssignmentStatus

    model_config = ConfigDict(from_attributes=True)


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
    is_overdue: bool
    assignments: list[TaskAssignmentResponse]

    model_config = ConfigDict(from_attributes=True)

# Task Comment
class TaskCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class TaskCommentResponse(BaseModel):
    id: int
    task_id: int
    user_id: int
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)