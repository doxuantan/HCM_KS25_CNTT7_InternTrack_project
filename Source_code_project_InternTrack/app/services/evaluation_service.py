from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation import Evaluation
from app.models.evaluation_detail import EvaluationDetail
from app.models.lecturer import Lecturer
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole


def _lecturer_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Lecturer.id).where(Lecturer.user_id == user.id))


def _assert_target_scope(db: Session, data, user: User) -> None:
    if (data.student_id is None) == (data.team_id is None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Chỉ định rõ sinh viên hoặc nhóm.")
    if user.role == UserRole.ADMIN:
        return
    if user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        if data.team_id is not None:
            team = db.get(Team, data.team_id)
            if team is not None and team.supervisor_id == lecturer_id:
                return
        if data.student_id is not None:
            allowed = db.scalar(
                select(TeamMember.id)
                .join(Team, Team.id == TeamMember.team_id)
                .where(TeamMember.student_id == data.student_id, Team.supervisor_id == lecturer_id)
                .limit(1)
            )
            if allowed is not None:
                return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền đánh giá đối tượng ngoài phạm vi.")


def list_evaluations(db: Session, user: User) -> list[dict]:
    statement = select(Evaluation)
    if user.role == UserRole.ADMIN:
        pass
    elif user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        team_ids = db.scalars(select(Team.id).where(Team.supervisor_id == lecturer_id)).all()
        student_ids = db.scalars(
            select(TeamMember.student_id).where(TeamMember.team_id.in_(team_ids))
        ).all()
        statement = statement.where(
            (Evaluation.team_id.in_(team_ids) if team_ids else False)
            | (Evaluation.student_id.in_(student_ids) if student_ids else False)
        )
    else:
        from app.models.student import Student
        student_id = db.scalar(select(Student.id).where(Student.user_id == user.id))
        statement = statement.where(
            (Evaluation.student_id == student_id) if student_id is not None else False
        )

    evaluations = db.scalars(statement.order_by(Evaluation.created_at.desc())).all()
    result = []
    for evaluation in evaluations:
        details = db.scalars(
            select(EvaluationDetail).where(EvaluationDetail.evaluation_id == evaluation.id)
        ).all()
        result.append({
            "id": evaluation.id,
            "student_id": evaluation.student_id,
            "team_id": evaluation.team_id,
            "evaluator_id": evaluation.evaluator_id,
            "period_id": evaluation.period_id,
            "total_score": evaluation.total_score,
            "comment": evaluation.comment,
            "is_published": evaluation.is_published,
            "created_at": evaluation.created_at,
            "details": [
                {"criteria_id": detail.criteria_id, "score": detail.score, "comment": detail.comment}
                for detail in details
            ],
        })
    return result


def create_evaluation(db: Session, data, user: User) -> dict:
    _assert_target_scope(db, data, user)
    total = sum((detail.score for detail in data.details), Decimal("0")) if data.details else None
    evaluation = Evaluation(
        student_id=data.student_id,
        team_id=data.team_id,
        evaluator_id=user.id,
        period_id=data.period_id,
        total_score=total,
        comment=data.comment,
        is_published=data.is_published,
    )
    db.add(evaluation)
    db.flush()
    db.add_all([
        EvaluationDetail(
            evaluation_id=evaluation.id,
            criteria_id=detail.criteria_id,
            score=detail.score,
            comment=detail.comment,
        )
        for detail in data.details
    ])
    db.commit()
    db.refresh(evaluation)
    for item in list_evaluations(db, user):
        if item["id"] == evaluation.id:
            return item
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
        "details": [],
    }