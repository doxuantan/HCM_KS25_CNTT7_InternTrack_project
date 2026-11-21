from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.progress import MemberProgressResponse, ProgressStatsResponse, TeamProgressResponse
from app.services import progress_service


router = APIRouter(
    prefix="/progress",
    tags=["Progress"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/me", response_model=MemberProgressResponse)
def get_my_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return progress_service.get_my_progress(db, current_user)


@router.get("/team/{team_id}", response_model=TeamProgressResponse)
def get_team_progress(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return progress_service.get_team_progress(db, team_id, current_user)


@router.get("/member/{student_id}", response_model=MemberProgressResponse)
def get_member_progress(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return progress_service.get_member_progress(db, student_id, current_user)


@router.get("/overview", response_model=ProgressStatsResponse)
def get_progress_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return progress_service.get_progress_overview(db, current_user)