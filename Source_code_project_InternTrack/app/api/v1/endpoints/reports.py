from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.report import ReportCreate, ReportResponse, ReportReviewResponse, ReportReviewUpdate
from app.services import report_service


router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[ReportResponse])
def list_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return report_service.list_reports(db, current_user)


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    data: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return report_service.create_report(db, data, current_user)


@router.post("/{report_id}/submit")
def submit_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return report_service.submit_report(db, report_id, current_user)


@router.get("/{report_id}/review", response_model=list[ReportReviewResponse])
def get_report_reviews(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return report_service.get_report_reviews(db, report_id, current_user)


@router.post("/{report_id}/review")
def review_report(
    report_id: int,
    data: ReportReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return report_service.review_report(db, report_id, data, current_user)