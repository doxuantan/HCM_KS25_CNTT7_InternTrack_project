import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.student import Student
from app.models.team_member import TeamMember
from app.models.user import User


logger = logging.getLogger(__name__)


def create_notification(
    db: Session,
    *,
    user_id: int,
    title: str,
    content: str,
    notification_type: str,
) -> Notification | None:
    notification = Notification(
        user_id=user_id,
        title=title,
        content=content,
        notification_type=notification_type,
    )
    db.add(notification)
    try:
        db.commit()
        db.refresh(notification)
        return notification
    except Exception:
        db.rollback()
        logger.exception("Không thể lưu thông báo.")
        return None


def notify_task_assigned(
    db: Session,
    *,
    student: Student,
    task_title: str,
    assigned_by: User,
) -> None:
    assignee = db.get(User, student.user_id)
    if assignee is None:
        return
    create_notification(
        db,
        user_id=assignee.id,
        title="Nhiệm vụ mới",
        content=f"Bạn được {assigned_by.full_name} giao nhiệm vụ: {task_title}",
        notification_type="TASK_ASSIGNED",
    )


def notify_schedule_created(
    db: Session,
    *,
    team_id: int,
    title: str,
    start_time,
    end_time,
) -> None:
    student_ids = db.scalars(
        select(TeamMember.student_id).where(TeamMember.team_id == team_id)
    ).all()
    for student_id in set(student_ids):
        student = db.get(Student, student_id)
        if student is None:
            continue
        assignee = db.get(User, student.user_id)
        if assignee is None:
            continue
        create_notification(
            db,
            user_id=assignee.id,
            title="Lịch họp mới",
            content=f"Cuộc họp: {title}. Thời gian: {start_time} đến {end_time}",
            notification_type="SCHEDULE_CREATED",
        )