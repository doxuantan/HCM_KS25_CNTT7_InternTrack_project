from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.diary import DiaryResponse, DiaryReviewUpdate
from app.services import diary_service


router = APIRouter(
    prefix="/diaries",
    tags=["Diaries"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[DiaryResponse])
def list_diaries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return diary_service.list_diaries(db, current_user)


@router.post("/{diary_id}/review")
def review_diary(
    diary_id: int,
    data: DiaryReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return diary_service.review_diary(db, diary_id, data, current_user)