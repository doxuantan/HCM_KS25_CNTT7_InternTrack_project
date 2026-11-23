from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.attachment import Attachment
from app.models.lecturer import Lecturer
from app.models.internship_period import InternshipPeriod
from app.models.report import Report, ReportStatus, ReportType
from app.models.report_review import ReportReview, ReportReviewStatus
from app.models.student import Student
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole
from app.services.notification_service import create_notification


def _lecturer_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Lecturer.id).where(Lecturer.user_id == user.id))


def _student_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Student.id).where(Student.user_id == user.id))


def _is_team_member(db: Session, team_id: int, student_id: int) -> bool:
    return db.scalar(
        select(TeamMember.id).where(
            TeamMember.team_id == team_id,
            TeamMember.student_id == student_id,
        )
    ) is not None


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


def _can_view(db: Session, report: Report, user: User) -> None:
    if user.role == UserRole.STUDENT:
        student_id = _student_id(db, user)
        if student_id is not None and (
            report.student_id == student_id
            or (report.team_id is not None and _is_team_member(db, report.team_id, student_id))
        ):
            return
    _can_access(db, report, user)


def _report_data(db: Session, report: Report) -> dict:
    owner_name = None
    if report.student_id is not None:
        student = db.get(Student, report.student_id)
        owner = db.get(User, student.user_id) if student else None
        owner_name = owner.full_name if owner else None
    elif report.team_id is not None:
        team = db.get(Team, report.team_id)
        owner_name = team.team_name if team else None
    return {
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
        "reviews": [
            {
                "id": review.id,
                "reviewer_id": review.reviewer_id,
                "content": review.content,
                "status": review.status.value,
                "created_at": review.created_at,
            }
            for review in sorted(report.reviews, key=lambda item: (item.created_at, item.id))
        ],
    }


def list_reports(db: Session, user: User) -> list[dict]:
    statement = select(Report).options(
        selectinload(Report.reviews),
        selectinload(Report.student).selectinload(Student.user),
        selectinload(Report.team),
    )
    if user.role == UserRole.ADMIN:
        pass
    elif user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        team_ids = select(Team.id).where(Team.supervisor_id == lecturer_id)
        student_ids = select(TeamMember.student_id).join(Team).where(Team.supervisor_id == lecturer_id)
        statement = statement.where(
            (Report.team_id.in_(team_ids))
            | (Report.student_id.in_(student_ids))
        )
    elif user.role == UserRole.STUDENT:
        student_id = _student_id(db, user)
        team_ids = select(TeamMember.team_id).where(TeamMember.student_id == student_id) if student_id else select(Team.id).where(False)
        statement = statement.where(
            (Report.student_id == student_id if student_id else False)
            | (Report.team_id.in_(team_ids))
        )
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xem báo cáo.")

    reports = db.scalars(statement.order_by(Report.created_at.desc())).unique().all()
    return [_report_data(db, report) for report in reports]


def create_report(db: Session, data, user: User) -> dict:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ sinh viên có thể tạo báo cáo.")
    if data.student_id is not None and data.team_id is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Chỉ định sinh viên hoặc nhóm, không chọn cả hai.")
    student_id = _student_id(db, user)
    if student_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tài khoản chưa có hồ sơ sinh viên.")
    if db.get(InternshipPeriod, data.period_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy kỳ thực tập.")

    report_student_id = data.student_id if data.student_id is not None else student_id
    if data.team_id is None:
        if report_student_id != student_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không thể tạo báo cáo cho sinh viên khác.")
        is_in_period = db.scalar(
            select(TeamMember.id)
            .join(Team, Team.id == TeamMember.team_id)
            .where(TeamMember.student_id == student_id, Team.period_id == data.period_id)
            .limit(1)
        )
        if is_in_period is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Sinh viên không thuộc nhóm trong kỳ thực tập này.")
        team_id = None
        period_id = data.period_id
    else:
        team = db.get(Team, data.team_id)
        if team is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhóm.")
        if not _is_team_member(db, team.id, student_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không thuộc nhóm của báo cáo.")
        if team.period_id != data.period_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Kỳ thực tập không khớp với nhóm.")
        team_id = team.id
        period_id = data.period_id

    report = Report(
        student_id=report_student_id if team_id is None else None,
        team_id=team_id,
        period_id=period_id,
        title=data.title.strip(),
        report_type=ReportType(data.report_type),
        status=ReportStatus.DRAFT,
    )
    db.add(report)
    db.commit()
    report = db.scalar(
        select(Report).options(selectinload(Report.reviews)).where(Report.id == report.id)
    )
    return _report_data(db, report)


def submit_report(db: Session, report_id: int, user: User) -> dict:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy báo cáo.")
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ sinh viên có thể nộp báo cáo.")
    _can_view(db, report, user)
    if report.status == ReportStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Báo cáo đã duyệt và không thể sửa hoặc nộp lại.")
    if report.status not in (ReportStatus.DRAFT, ReportStatus.REVISION_REQUIRED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Báo cáo hiện không thể nộp.")

    attachment = db.scalar(
        select(Attachment)
        .where(
            Attachment.report_id == report.id,
            Attachment.mime_type.in_(
                (
                    "application/pdf",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            ),
        )
        .order_by(Attachment.uploaded_at.desc(), Attachment.id.desc())
        .limit(1)
    )
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Hãy tải lên tệp PDF hoặc DOCX trước khi nộp.")

    report.status = ReportStatus.SUBMITTED
    report.submitted_at = datetime.now()
    report.file_url = f"/api/v1/attachments/{attachment.id}"
    db.commit()
    return {"message": "Đã nộp báo cáo.", "report_id": report.id, "status": report.status.value}


def get_report_reviews(db: Session, report_id: int, user: User) -> list[dict]:
    report = db.scalar(
        select(Report).options(selectinload(Report.reviews)).where(Report.id == report_id)
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy báo cáo.")
    _can_view(db, report, user)
    return _report_data(db, report)["reviews"]


def _notify_report_target(db: Session, report: Report, *, status_value: ReportReviewStatus) -> None:
    if report.student_id is not None:
        user_ids = select(Student.user_id).where(Student.id == report.student_id)
    else:
        user_ids = select(Student.user_id).join(TeamMember).where(TeamMember.team_id == report.team_id)
    target_users = db.scalars(user_ids).all()
    title = "Báo cáo được duyệt" if status_value == ReportReviewStatus.APPROVED else "Báo cáo cần chỉnh sửa"
    content = (
        f"Báo cáo “{report.title}” đã được duyệt."
        if status_value == ReportReviewStatus.APPROVED
        else f"Báo cáo “{report.title}” cần được chỉnh sửa theo nhận xét của giảng viên."
    )
    for user_id in set(target_users):
        create_notification(
            db,
            user_id=user_id,
            title=title,
            content=content,
            notification_type=f"REPORT_{status_value.value}:{report.id}",
        )


def review_report(db: Session, report_id: int, data, user: User) -> dict:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy báo cáo.")
    _can_access(db, report, user)
    if report.status == ReportStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Báo cáo đã được duyệt và bị khóa.")
    if report.status not in (ReportStatus.SUBMITTED, ReportStatus.REVIEWING):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chỉ có thể nhận xét báo cáo đã nộp.")

    review_status = ReportReviewStatus(data.status)
    report.status = {
        ReportReviewStatus.APPROVED: ReportStatus.APPROVED,
        ReportReviewStatus.REVISION_REQUIRED: ReportStatus.REVISION_REQUIRED,
        ReportReviewStatus.REVIEWING: ReportStatus.REVIEWING,
    }[review_status]
    db.add(ReportReview(
        report_id=report.id,
        reviewer_id=user.id,
        content=data.content.strip(),
        status=review_status,
    ))
    db.commit()
    db.refresh(report)
    if review_status in (ReportReviewStatus.APPROVED, ReportReviewStatus.REVISION_REQUIRED):
        _notify_report_target(db, report, status_value=review_status)
    return {"message": "Đã cập nhật kết quả duyệt báo cáo.", "status": review_status.value, "report_id": report.id}
