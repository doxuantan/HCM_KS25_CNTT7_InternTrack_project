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
from app.schemas.team import (
    TeamCreate,
    TeamLeaderUpdate,
    TeamMemberAdd,
    TeamSupervisorUpdate,
    TeamUpdate,
)


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
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy nhóm.",
        )
    statement = _team_query_for_user(db, user)
    allowed = user.role == UserRole.ADMIN
    if statement is not None:
        allowed = db.scalar(statement.where(Team.id == team_id)) is not None
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập nhóm ngoài phạm vi.",
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
        if data.supervisor_id is not None and data.supervisor_id != supervisor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Giảng viên chỉ được tạo nhóm thuộc phạm vi của mình.",
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


def _require_team_member_manager(db: Session, team: Team, user: User) -> None:
    if user.role == UserRole.ADMIN:
        return
    if user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        if lecturer_id == team.supervisor_id:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Giảng viên không có quyền quản lý thành viên nhóm ngoài phạm vi.",
        )
    if user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ quản trị viên hoặc nhóm trưởng được quản lý thành viên.",
        )
    student_id = _student_id(db, user)
    membership = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == team.id,
            TeamMember.student_id == student_id,
            TeamMember.is_leader.is_(True),
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ quản trị viên hoặc nhóm trưởng được quản lý thành viên.",
        )


def _ensure_student_not_in_period(
    db: Session,
    student_id: int,
    period_id: int,
    *,
    exclude_team_id: int | None = None,
) -> None:
    statement = (
        select(TeamMember.id)
        .join(Team, TeamMember.team_id == Team.id)
        .where(
            TeamMember.student_id == student_id,
            Team.period_id == period_id,
        )
    )
    if exclude_team_id is not None:
        statement = statement.where(Team.id != exclude_team_id)
    if db.scalar(statement) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sinh viên đã tham gia một nhóm khác trong cùng kỳ thực tập (BR05).",
        )


def add_team_member(
    db: Session,
    team_id: int,
    data: TeamMemberAdd,
    user: User,
) -> TeamMember:
    team = get_team(db, team_id, user)
    _require_team_member_manager(db, team, user)
    if db.get(Student, data.student_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sinh viên.",
        )
    existing = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.student_id == data.student_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sinh viên đã là thành viên của nhóm này.",
        )
    _ensure_student_not_in_period(db, data.student_id, team.period_id)

    member = TeamMember(team_id=team_id, student_id=data.student_id, is_leader=False)
    db.add(member)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể thêm sinh viên; dữ liệu thành viên không hợp lệ.",
        ) from None
    db.refresh(member)
    return member


def remove_team_member(
    db: Session,
    team_id: int,
    student_id: int,
    user: User,
) -> None:
    team = get_team(db, team_id, user)
    _require_team_member_manager(db, team, user)
    member = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.student_id == student_id,
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy thành viên trong nhóm.",
        )
    if member.is_leader:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể xóa nhóm trưởng; hãy thay đổi nhóm trưởng trước.",
        )
    db.delete(member)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể xóa thành viên khỏi nhóm.",
        ) from None


def list_team_members(db: Session, team_id: int, user: User) -> list[dict]:
    team = get_team(db, team_id, user)
    rows = db.execute(
        select(
            TeamMember,
            Student.student_code,
            User.full_name,
        )
        .join(Student, TeamMember.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .where(TeamMember.team_id == team.id)
        .order_by(TeamMember.is_leader.desc(), User.full_name.asc())
    ).all()
    return [
        {
            "id": member.id,
            "team_id": member.team_id,
            "student_id": member.student_id,
            "is_leader": member.is_leader,
            "joined_at": member.joined_at,
            "student_name": student_name,
            "student_code": student_code,
        }
        for member, student_code, student_name in rows
    ]


def change_team_leader(
    db: Session,
    team_id: int,
    data: TeamLeaderUpdate,
    user: User,
) -> TeamMember:
    team = get_team(db, team_id, user)
    can_manage = user.role == UserRole.ADMIN
    if user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        can_manage = lecturer_id == team.supervisor_id
    elif user.role == UserRole.STUDENT:
        student_id = _student_id(db, user)
        can_manage = student_id is not None and db.scalar(
            select(TeamMember.id).where(
                TeamMember.team_id == team.id,
                TeamMember.student_id == student_id,
                TeamMember.is_leader.is_(True),
            )
        ) is not None
    if not can_manage:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ quản trị viên, giảng viên phụ trách hoặc nhóm trưởng được thay đổi nhóm trưởng.",
        )
    student_id = data.student_id if data.student_id is not None else data.leader_id
    if student_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="student_id là bắt buộc.",
        )
    member = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.student_id == student_id,
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sinh viên không phải thành viên của nhóm.",
        )

    for current in db.scalars(select(TeamMember).where(TeamMember.team_id == team_id)):
        current.is_leader = current.id == member.id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể cập nhật nhóm trưởng.",
        ) from None
    db.refresh(member)
    return member


def change_team_supervisor(
    db: Session,
    team_id: int,
    data: TeamSupervisorUpdate,
    user: User,
) -> Team:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ quản trị viên được thay đổi giảng viên hướng dẫn.",
        )
    team = get_team(db, team_id, user)
    supervisor_id = (
        data.supervisor_id
        if data.supervisor_id is not None
        else data.lecturer_id
    )
    if supervisor_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="supervisor_id là bắt buộc.",
        )
    if db.get(Lecturer, supervisor_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy giảng viên hướng dẫn.",
        )
    team.supervisor_id = supervisor_id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể cập nhật giảng viên hướng dẫn.",
        ) from None
    db.refresh(team)
    return team