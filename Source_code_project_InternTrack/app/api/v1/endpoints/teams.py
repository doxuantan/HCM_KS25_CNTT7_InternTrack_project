from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.dependencies.permissions import require_role
from app.models.internship_period import InternshipPeriod
from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole
from app.schemas.team import (
    StudentTeamResponse,
    TeamPeriodResponse,
    TeamStudentResponse,
    TeamSupervisorResponse,
)


router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/me", response_model=list[StudentTeamResponse])
def get_my_teams(
    user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
) -> list[StudentTeamResponse]:
    student_id = db.scalar(select(Student.id).where(Student.user_id == user.id))
    if student_id is None:
        return []

    teams = db.scalars(
        select(Team)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .join(InternshipPeriod, InternshipPeriod.id == Team.period_id)
        .where(TeamMember.student_id == student_id)
        .options(
            selectinload(Team.period),
            selectinload(Team.supervisor).selectinload(Lecturer.user),
            selectinload(Team.members)
            .selectinload(TeamMember.student)
            .selectinload(Student.user),
        )
        .order_by(InternshipPeriod.start_date.desc(), Team.id)
    ).all()

    return [
        StudentTeamResponse(
            id=team.id,
            team_name=team.team_name,
            team_code=team.team_code,
            description=team.description,
            status=team.status,
            period=TeamPeriodResponse.model_validate(team.period),
            supervisor=TeamSupervisorResponse(
                full_name=team.supervisor.user.full_name,
                email=team.supervisor.user.email,
            ),
            members=[
                TeamStudentResponse(
                    student_code=member.student.student_code,
                    full_name=member.student.user.full_name,
                    email=member.student.user.email,
                    is_leader=member.is_leader,
                )
                for member in team.members
            ],
        )
        for team in teams
    ]