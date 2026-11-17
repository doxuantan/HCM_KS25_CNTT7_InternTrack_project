from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_role
from app.models.user import User, UserRole
from app.schemas.team import TeamCreate, TeamResponse, TeamUpdate
from app.services import team_service


router = APIRouter(
    prefix="/teams",
    tags=["Teams"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[TeamResponse])
def list_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TeamResponse]:
    return team_service.get_teams(db, current_user)


@router.get("/{team_id}", response_model=TeamResponse)
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamResponse:
    return team_service.get_team(db, team_id, current_user)


@router.post(
    "",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.SUPERVISOR))],
)
def create_team(
    data: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamResponse:
    return team_service.create_team(db, data, current_user)


@router.put(
    "/{team_id}",
    response_model=TeamResponse,
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.SUPERVISOR))],
)
def update_team(
    team_id: int,
    data: TeamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamResponse:
    return team_service.update_team(db, team_id, data, current_user)