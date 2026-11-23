from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.internship_diary import DiaryStatus
from app.models.user import User
from app.schemas.diary import DiaryCreate, DiaryResponse, DiaryReviewResponse, DiaryReviewUpdate
from app.services import diary_service


router = APIRouter(
    prefix="/diaries",
    tags=["Diaries"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[DiaryResponse])
def list_diaries(
    student_id: int | None = Query(default=None, gt=0),
    work_date: date | None = None,
    diary_status: DiaryStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return diary_service.list_diaries(
        db,
        current_user,
        student_id=student_id,
        work_date=work_date,
        status_filter=diary_status,
    )


@router.post("", response_model=DiaryResponse, status_code=201)
def create_diary(
    data: DiaryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return diary_service.create_diary(db, data, current_user)


@router.put("/{diary_id}", response_model=DiaryResponse)
def update_diary(
    diary_id: int,
    data: DiaryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return diary_service.update_diary(db, diary_id, data, current_user)


@router.get("/{diary_id}/review", response_model=list[DiaryReviewResponse])
def get_diary_reviews(
    diary_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return diary_service.get_diary_reviews(db, diary_id, current_user)


@router.post("/{diary_id}/review")
def review_diary(
    diary_id: int,
    data: DiaryReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return diary_service.review_diary(db, diary_id, data, current_user)