from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_role
from app.models.user import User, UserRole
from app.schemas.team import (
    TeamCreate,
    TeamLeaderUpdate,
    TeamMemberAdd,
    TeamMemberResponse,
    TeamMemberDetail,
    TeamResponse,
    TeamSupervisorUpdate,
    TeamUpdate,
)
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


@router.get("/{team_id}/members", response_model=list[TeamMemberDetail])
def list_team_members(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return team_service.list_team_members(db, team_id, current_user)


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


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    team_service.delete_team(db, team_id, current_user)


@router.post(
    "/{team_id}/members",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_team_member(
    team_id: int,
    data: TeamMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamMemberResponse:
    return team_service.add_team_member(db, team_id, data, current_user)


@router.delete("/{team_id}/members/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_team_member(
    team_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    team_service.remove_team_member(db, team_id, student_id, current_user)


@router.patch("/{team_id}/leader", response_model=TeamMemberResponse)
def change_team_leader(
    team_id: int,
    data: TeamLeaderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamMemberResponse:
    return team_service.change_team_leader(db, team_id, data, current_user)


@router.put("/{team_id}/leader", response_model=TeamMemberResponse)
def replace_team_leader(
    team_id: int,
    data: TeamLeaderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamMemberResponse:
    return team_service.change_team_leader(db, team_id, data, current_user)


@router.patch("/{team_id}/supervisor", response_model=TeamResponse)
def change_team_supervisor(
    team_id: int,
    data: TeamSupervisorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamResponse:
    return team_service.change_team_supervisor(db, team_id, data, current_user)


@router.put("/{team_id}/supervisor", response_model=TeamResponse)
def replace_team_supervisor(
    team_id: int,
    data: TeamSupervisorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamResponse:
    return team_service.change_team_supervisor(db, team_id, data, current_user)