from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.evaluation import Evaluation
from app.models.evaluation_criteria import EvaluationCriteria
from app.models.evaluation_detail import EvaluationDetail
from app.models.internship_period import InternshipPeriod
from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole
from app.services.notification_service import create_notification

MAX_SCORE = Decimal("999.99")


def _lecturer_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Lecturer.id).where(Lecturer.user_id == user.id))


def _student_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Student.id).where(Student.user_id == user.id))


def _assert_target_scope(db: Session, data, user: User) -> None:
    if (data.student_id is None) == (data.team_id is None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Chỉ định rõ sinh viên hoặc nhóm.")
    if db.get(InternshipPeriod, data.period_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy kỳ thực tập.")
    if data.team_id is not None:
        team = db.get(Team, data.team_id)
        if team is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhóm.")
        if team.period_id != data.period_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Kỳ thực tập không khớp với nhóm.")
        if user.role == UserRole.ADMIN:
            return
        lecturer_id = _lecturer_id(db, user)
        if user.role == UserRole.SUPERVISOR and team.supervisor_id == lecturer_id:
            return
    elif data.student_id is not None:
        student = db.get(Student, data.student_id)
        if student is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy sinh viên.")
        target_team = db.scalar(
            select(TeamMember.id)
            .join(Team, Team.id == TeamMember.team_id)
            .where(TeamMember.student_id == data.student_id, Team.period_id == data.period_id)
            .limit(1)
        )
        if target_team is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Sinh viên không thuộc nhóm trong kỳ thực tập này.")
        if user.role == UserRole.ADMIN:
            return
        lecturer_id = _lecturer_id(db, user)
        allowed = db.scalar(
            select(TeamMember.id)
            .join(Team, Team.id == TeamMember.team_id)
            .where(
                TeamMember.student_id == data.student_id,
                Team.period_id == data.period_id,
                Team.supervisor_id == lecturer_id,
            )
            .limit(1)
        )
        if user.role == UserRole.SUPERVISOR and allowed is not None:
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền đánh giá đối tượng ngoài phạm vi.")


def _assert_evaluation_access(db: Session, evaluation: Evaluation, user: User) -> None:
    target = SimpleNamespace(
        student_id=evaluation.student_id,
        team_id=evaluation.team_id,
        period_id=evaluation.period_id,
    )
    _assert_target_scope(db, target, user)


def _detail_records(evaluation: Evaluation) -> list[dict]:
    return [
        {
            "criteria_id": detail.criteria_id,
            "score": detail.score,
            "comment": detail.comment,
            "criteria_name": detail.criteria.name if detail.criteria else None,
            "weight": detail.criteria.weight if detail.criteria else None,
        }
        for detail in evaluation.details
    ]


def _evaluation_data(evaluation: Evaluation) -> dict:
    return {
        "id": evaluation.id,
        "student_id": evaluation.student_id,
        "team_id": evaluation.team_id,
        "evaluator_id": evaluation.evaluator_id,
        "period_id": evaluation.period_id,
        "total_score": evaluation.total_score,
        "comment": evaluation.comment,
        "is_published": evaluation.is_published,
        "created_at": evaluation.created_at,
        "details": _detail_records(evaluation),
    }


def _load_evaluation(db: Session, evaluation_id: int) -> Evaluation | None:
    return db.scalar(
        select(Evaluation)
        .options(
            selectinload(Evaluation.details).selectinload(EvaluationDetail.criteria)
        )
        .where(Evaluation.id == evaluation_id)
    )


def list_evaluations(db: Session, user: User) -> list[dict]:
    statement = select(Evaluation).options(
        selectinload(Evaluation.details).selectinload(EvaluationDetail.criteria)
    )
    if user.role == UserRole.ADMIN:
        pass
    elif user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        team_ids = select(Team.id).where(Team.supervisor_id == lecturer_id)
        student_ids = select(TeamMember.student_id).join(Team).where(Team.supervisor_id == lecturer_id)
        statement = statement.where(
            Evaluation.team_id.in_(team_ids)
            | Evaluation.student_id.in_(student_ids)
        )
    elif user.role == UserRole.STUDENT:
        student_id = _student_id(db, user)
        team_ids = (
            select(TeamMember.team_id).where(TeamMember.student_id == student_id)
            if student_id
            else select(Team.id).where(False)
        )
        statement = statement.where(
            Evaluation.is_published.is_(True),
            (
                (Evaluation.student_id == student_id if student_id else False)
                | Evaluation.team_id.in_(team_ids)
            ),
        )
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xem đánh giá.")
    evaluations = db.scalars(statement.order_by(Evaluation.created_at.desc())).unique().all()
    return [_evaluation_data(evaluation) for evaluation in evaluations]


def get_evaluation(db: Session, evaluation_id: int, user: User) -> dict:
    evaluation = _load_evaluation(db, evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiếu đánh giá.")
    if user.role == UserRole.STUDENT:
        if not evaluation.is_published:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiếu đánh giá.")
        student_id = _student_id(db, user)
        allowed = student_id is not None and (
            evaluation.student_id == student_id
            or (
                evaluation.team_id is not None
                and db.scalar(
                    select(TeamMember.id).where(
                        TeamMember.team_id == evaluation.team_id,
                        TeamMember.student_id == student_id,
                    )
                ) is not None
            )
        )
        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xem phiếu đánh giá này.")
    else:
        _assert_evaluation_access(db, evaluation, user)
    return _evaluation_data(evaluation)


def list_criteria(db: Session, user: User) -> list[dict]:
    if user.role not in (UserRole.ADMIN, UserRole.SUPERVISOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xem tiêu chí đánh giá.")
    criteria = db.scalars(
        select(EvaluationCriteria)
        .where(EvaluationCriteria.is_active.is_(True))
        .order_by(EvaluationCriteria.id)
    ).all()
    return [
        {"id": item.id, "name": item.name, "description": item.description, "weight": item.weight}
        for item in criteria
    ]


def _validate_details(db: Session, details) -> Decimal | None:
    criteria_ids = [item.criteria_id for item in details]
    if len(criteria_ids) != len(set(criteria_ids)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Mỗi tiêu chí chỉ được nhập một lần.")
    for item in details:
        criteria = db.get(EvaluationCriteria, item.criteria_id)
        if criteria is None or not criteria.is_active:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Tiêu chí không tồn tại hoặc đã bị vô hiệu hóa.")
        if item.score > MAX_SCORE:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Điểm tiêu chí vượt giới hạn.")
    total = sum((item.score for item in details), Decimal("0")) if details else None
    if total is not None and total > MAX_SCORE:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Tổng điểm vượt giới hạn lưu trữ.")
    return total


def _add_details(db: Session, evaluation: Evaluation, details) -> None:
    total = _validate_details(db, details)
    for existing in list(evaluation.details):
        db.delete(existing)
    db.flush()
    evaluation.details = [
        EvaluationDetail(
            criteria_id=item.criteria_id,
            score=item.score,
            comment=item.comment,
        )
        for item in details
    ]
    evaluation.total_score = total


def _notify_evaluation_target(db: Session, evaluation: Evaluation) -> None:
    if evaluation.student_id is not None:
        user_ids = select(Student.user_id).where(Student.id == evaluation.student_id)
    else:
        user_ids = select(Student.user_id).join(TeamMember).where(TeamMember.team_id == evaluation.team_id)
    for user_id in set(db.scalars(user_ids).all()):
        create_notification(
            db,
            user_id=user_id,
            title="Bảng đánh giá đã được công bố",
            content="Giảng viên đã công bố kết quả đánh giá thực tập của bạn.",
            notification_type=f"EVALUATION_PUBLISHED:{evaluation.id}",
        )


def create_evaluation(db: Session, data, user: User) -> dict:
    if user.role not in (UserRole.ADMIN, UserRole.SUPERVISOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ quản trị viên hoặc giảng viên mới có thể tạo đánh giá.")
    _assert_target_scope(db, data, user)
    total = _validate_details(db, data.details)
    evaluation = Evaluation(
        student_id=data.student_id,
        team_id=data.team_id,
        evaluator_id=user.id,
        period_id=data.period_id,
        total_score=total,
        comment=data.comment.strip() if data.comment else None,
        is_published=data.is_published,
    )
    db.add(evaluation)
    db.flush()
    evaluation.details = [
        EvaluationDetail(
            criteria_id=detail.criteria_id,
            score=detail.score,
            comment=detail.comment,
        )
        for detail in data.details
    ]
    db.commit()
    if evaluation.is_published:
        _notify_evaluation_target(db, evaluation)
    refreshed = _load_evaluation(db, evaluation.id)
    return _evaluation_data(refreshed)


def update_evaluation(db: Session, evaluation_id: int, data, user: User) -> dict:
    evaluation = _load_evaluation(db, evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiếu đánh giá.")
    _assert_evaluation_access(db, evaluation, user)
    if user.role not in (UserRole.ADMIN, UserRole.SUPERVISOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền cập nhật đánh giá.")
    if evaluation.is_published:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phiếu đã công bố và không thể chỉnh sửa.")
    if data.is_published:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Dùng thao tác công bố riêng cho phiếu đánh giá.")
    _assert_target_scope(db, data, user)
    evaluation.student_id = data.student_id
    evaluation.team_id = data.team_id
    evaluation.period_id = data.period_id
    evaluation.comment = data.comment.strip() if data.comment else None
    _add_details(db, evaluation, data.details)
    db.commit()
    return _evaluation_data(_load_evaluation(db, evaluation.id))


def delete_evaluation(db: Session, evaluation_id: int, user: User) -> None:
    evaluation = _load_evaluation(db, evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiếu đánh giá.")
    _assert_evaluation_access(db, evaluation, user)
    if user.role not in (UserRole.ADMIN, UserRole.SUPERVISOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xóa đánh giá.")
    if evaluation.is_published:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phiếu đã công bố và không thể xóa.")
    db.delete(evaluation)
    db.commit()


def publish_evaluation(db: Session, evaluation_id: int, user: User) -> dict:
    evaluation = _load_evaluation(db, evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiếu đánh giá.")
    _assert_evaluation_access(db, evaluation, user)
    if user.role not in (UserRole.ADMIN, UserRole.SUPERVISOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ quản trị viên hoặc giảng viên mới có thể công bố đánh giá.")
    if not evaluation.is_published:
        evaluation.is_published = True
        db.commit()
        _notify_evaluation_target(db, evaluation)
    return _evaluation_data(_load_evaluation(db, evaluation.id))
