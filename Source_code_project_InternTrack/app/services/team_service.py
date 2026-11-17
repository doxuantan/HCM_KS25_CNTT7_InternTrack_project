from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.internship_period import InternshipPeriod
from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole
from app.schemas.team import TeamCreate, TeamUpdate


def _lecturer_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Lecturer.id).where(Lecturer.user_id == user.id))


def _student_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Student.id).where(Student.user_id == user.id))


def _team_query_for_user(db: Session, user: User):
    statement = select(Team)
    if user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        if lecturer_id is None:
            return None
        statement = statement.where(Team.supervisor_id == lecturer_id)
    elif user.role == UserRole.STUDENT:
        student_id = _student_id(db, user)
        if student_id is None:
            return None
        statement = statement.join(TeamMember).where(
            TeamMember.student_id == student_id
        )
    return statement


def get_teams(db: Session, user: User) -> list[Team]:
    statement = _team_query_for_user(db, user)
    if statement is None:
        return []
    return db.scalars(statement.order_by(Team.id.desc())).unique().all()


def get_team(db: Session, team_id: int, user: User) -> Team:
    statement = _team_query_for_user(db, user)
    if statement is None:
        team = None
    else:
        team = db.scalar(statement.where(Team.id == team_id))
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy nhóm.",
        )
    return team


def _validate_references(
    db: Session,
    period_id: int,
    supervisor_id: int,
) -> None:
    if db.get(InternshipPeriod, period_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy kỳ thực tập.",
        )
    if db.get(Lecturer, supervisor_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy giảng viên hướng dẫn.",
        )


def _ensure_unique_code(
    db: Session,
    team_code: str,
    *,
    exclude_team_id: int | None = None,
) -> None:
    statement = select(Team.id).where(Team.team_code == team_code)
    if exclude_team_id is not None:
        statement = statement.where(Team.id != exclude_team_id)
    if db.scalar(statement) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mã nhóm đã tồn tại.",
        )


def create_team(db: Session, data: TeamCreate, user: User) -> Team:
    if user.role == UserRole.SUPERVISOR:
        supervisor_id = _lecturer_id(db, user)
        if supervisor_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản chưa được liên kết với hồ sơ giảng viên.",
            )
    else:
        supervisor_id = data.supervisor_id
        if supervisor_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="supervisor_id là bắt buộc khi ADMIN tạo nhóm.",
            )

    _validate_references(db, data.period_id, supervisor_id)
    _ensure_unique_code(db, data.team_code)
    team = Team(
        period_id=data.period_id,
        supervisor_id=supervisor_id,
        team_name=data.team_name,
        team_code=data.team_code,
        description=data.description,
        status=data.status,
    )
    db.add(team)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mã nhóm đã tồn tại hoặc dữ liệu liên kết không hợp lệ.",
        ) from None
    db.refresh(team)
    return team


def update_team(
    db: Session,
    team_id: int,
    data: TeamUpdate,
    user: User,
) -> Team:
    team = get_team(db, team_id, user)
    update_data = data.model_dump(exclude_unset=True)

    if user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        if "supervisor_id" in update_data and update_data["supervisor_id"] != lecturer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Giảng viên không thể chuyển quyền quản lý nhóm.",
            )
        update_data.pop("supervisor_id", None)

    period_id = update_data.get("period_id", team.period_id)
    supervisor_id = update_data.get("supervisor_id", team.supervisor_id)
    _validate_references(db, period_id, supervisor_id)
    if "team_code" in update_data:
        _ensure_unique_code(db, update_data["team_code"], exclude_team_id=team.id)

    for field, value in update_data.items():
        setattr(team, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mã nhóm đã tồn tại hoặc dữ liệu liên kết không hợp lệ.",
        ) from None
    db.refresh(team)
    return team