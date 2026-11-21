from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class EvaluationDetailCreate(BaseModel):
    criteria_id: int = Field(gt=0)
    score: Decimal = Field(ge=0)
    comment: str | None = Field(default=None, max_length=2000)


class EvaluationCreate(BaseModel):
    student_id: int | None = Field(default=None, gt=0)
    team_id: int | None = Field(default=None, gt=0)
    period_id: int = Field(gt=0)
    comment: str | None = Field(default=None, max_length=5000)
    is_published: bool = False
    details: list[EvaluationDetailCreate] = []


class EvaluationDetailResponse(BaseModel):
    criteria_id: int
    score: Decimal
    comment: str | None = None


class EvaluationResponse(BaseModel):
    id: int
    student_id: int | None = None
    team_id: int | None = None
    evaluator_id: int
    period_id: int
    total_score: Decimal | None = None
    comment: str | None = None
    is_published: bool
    created_at: datetime
    details: list[EvaluationDetailResponse] = []

    model_config = ConfigDict(from_attributes=True)