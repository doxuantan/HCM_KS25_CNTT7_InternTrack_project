from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lecturer import Lecturer
from app.models.report import Report, ReportStatus
from app.models.report_review import ReportReview, ReportReviewStatus
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole
from app.models.student import Student


def _lecturer_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Lecturer.id).where(Lecturer.user_id == user.id))


def _can_access(db: Session, report: Report, user: User) -> None:
    if user.role == UserRole.ADMIN:
        return
    if user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        allowed_team = report.team_id is not None and db.scalar(
            select(Team.id).where(Team.id == report.team_id, Team.supervisor_id == lecturer_id)
        ) is not None
        allowed_member = report.student_id is not None and db.scalar(
            select(TeamMember.id)
            .join(Team, Team.id == TeamMember.team_id)
            .where(TeamMember.student_id == report.student_id, Team.supervisor_id == lecturer_id)
            .limit(1)
        ) is not None
        if allowed_team or allowed_member:
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xem hoặc duyệt báo cáo này.")


def list_reports(db: Session, user: User) -> list[dict]:
    statement = select(Report)
    if user.role == UserRole.ADMIN:
        pass
    elif user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        team_ids = db.scalars(select(Team.id).where(Team.supervisor_id == lecturer_id)).all()
        student_ids = db.scalars(
            select(TeamMember.student_id).where(TeamMember.team_id.in_(team_ids))
        ).all()
        statement = statement.where(
            (Report.team_id.in_(team_ids) if team_ids else False)
            | (Report.student_id.in_(student_ids) if student_ids else False)
        )
    else:
        student_id = db.scalar(select(Student.id).where(Student.user_id == user.id))
        statement = statement.where(
            (Report.student_id == student_id) if student_id is not None else False
        )

    reports = db.scalars(statement.order_by(Report.created_at.desc())).all()
    result = []
    for report in reports:
        owner_name = None
        if report.student_id is not None:
            student = db.get(Student, report.student_id)
            owner = db.get(User, student.user_id) if student else None
            owner_name = owner.full_name if owner else None
        elif report.team_id is not None:
            team = db.get(Team, report.team_id)
            owner_name = team.team_name if team else None
        result.append({
            "id": report.id,
            "student_id": report.student_id,
            "team_id": report.team_id,
            "period_id": report.period_id,
            "title": report.title,
            "report_type": report.report_type.value,
            "file_url": report.file_url,
            "status": report.status.value,
            "submitted_at": report.submitted_at,
            "created_at": report.created_at,
            "owner_name": owner_name,
        })
    return result


def review_report(db: Session, report_id: int, data, user: User) -> dict:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy báo cáo.")
    _can_access(db, report, user)
    review_status = ReportReviewStatus(data.status)
    if review_status == ReportReviewStatus.APPROVED:
        report.status = ReportStatus.APPROVED
    elif review_status == ReportReviewStatus.REVISION_REQUIRED:
        report.status = ReportStatus.REVISION_REQUIRED
    else:
        report.status = ReportStatus.REVIEWING
    db.add(ReportReview(
        report_id=report.id,
        reviewer_id=user.id,
        content=data.content,
        status=review_status,
    ))
    db.commit()
    db.refresh(report)
    return {"message": "Đã cập nhật kết quả duyệt báo cáo.", "status": review_status.value, "report_id": report.id}