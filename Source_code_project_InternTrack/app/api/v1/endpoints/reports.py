from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.report import ReportResponse, ReportReviewUpdate
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


@router.post("/{report_id}/review")
def review_report(
    report_id: int,
    data: ReportReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return report_service.review_report(db, report_id, data, current_user)