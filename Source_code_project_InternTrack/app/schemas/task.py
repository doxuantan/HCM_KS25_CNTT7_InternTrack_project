import enum
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
    student_id: int | None = Field(default=None, gt=0)
    student_ids: list[int] | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_assignees(self):
        if (self.student_id is None) == (self.student_ids is None):
            raise ValueError("Provide either student_id or student_ids.")
        if self.student_ids is not None:
            if any(student_id <= 0 for student_id in self.student_ids):
                raise ValueError("Student IDs must be positive.")
            if len(set(self.student_ids)) != len(self.student_ids):
                raise ValueError("Student IDs must be unique.")
        return self

    @property
    def assignee_ids(self) -> list[int]:
        if self.student_ids is not None:
            return self.student_ids
        if self.student_id is not None:
            return [self.student_id]
        raise ValueError("An assignee is required.")


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TaskProgressUpdate(BaseModel):
    progress: int = Field(strict=True, ge=0, le=100)


class TaskReviewStatus(str, enum.Enum):
    APPROVED = "APPROVED"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    REJECTED = "REJECTED"


class TaskReviewUpdate(BaseModel):
    status: TaskReviewStatus
    comment: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_review_comment(self):
        if self.status == TaskReviewStatus.REJECTED:
            if not self.comment or not self.comment.strip():
                raise ValueError("Rejection reason is required.")
        return self


class TaskAssignmentResponse(BaseModel):
    id: int
    task_id: int
    student_id: int
    assigned_by: int
    assigned_at: datetime
    progress: int
    status: AssignmentStatus
    student_name: str | None = None
    student_code: str | None = None

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


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class TaskReviewResponse(BaseModel):
    message: str
    status: TaskReviewStatus
    task: TaskResponse


# Task Comment
class TaskCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class TaskCommentResponse(BaseModel):
    id: int
    task_id: int
    user_id: int
    content: str
    created_at: datetime
    user_name: str | None = None

    model_config = ConfigDict(from_attributes=True)