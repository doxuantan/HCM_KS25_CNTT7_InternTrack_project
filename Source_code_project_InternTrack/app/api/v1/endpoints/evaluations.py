from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.evaluation import EvaluationCreate, EvaluationCriteriaResponse, EvaluationResponse
from app.services import evaluation_service


router = APIRouter(
    prefix="/evaluations",
    tags=["Evaluations"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[EvaluationResponse])
def list_evaluations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return evaluation_service.list_evaluations(db, current_user)


@router.get("/criteria", response_model=list[EvaluationCriteriaResponse])
def list_evaluation_criteria(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return evaluation_service.list_criteria(db, current_user)


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return evaluation_service.get_evaluation(db, evaluation_id, current_user)


@router.post("", response_model=EvaluationResponse, status_code=status.HTTP_201_CREATED)
def create_evaluation(
    data: EvaluationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return evaluation_service.create_evaluation(db, data, current_user)


@router.put("/{evaluation_id}", response_model=EvaluationResponse)
def update_evaluation(
    evaluation_id: int,
    data: EvaluationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return evaluation_service.update_evaluation(db, evaluation_id, data, current_user)


@router.post("/{evaluation_id}/publish", response_model=EvaluationResponse)
def publish_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return evaluation_service.publish_evaluation(db, evaluation_id, current_user)


@router.delete("/{evaluation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    evaluation_service.delete_evaluation(db, evaluation_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)