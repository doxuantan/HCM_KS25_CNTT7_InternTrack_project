import logging
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.student import Student
from app.models.task import Task, TaskStatus
from app.models.task_assignment import TaskAssignment
from app.models.team_member import TeamMember
from app.models.user import User


logger = logging.getLogger(__name__)
TASK_DEADLINE_REMINDER_WINDOW = timedelta(hours=24)


def list_notifications(db: Session, user: User) -> list[Notification]:
    scan_task_deadline_notifications(db)
    return db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
    ).all()


def list_unread_notifications(db: Session, user: User) -> list[Notification]:
    scan_task_deadline_notifications(db)
    return db.scalars(
        select(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
        .order_by(Notification.created_at.desc())
    ).all()


def mark_notification_read(db: Session, notification_id: int, user: User) -> None:
    notification = db.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông báo.")
    if notification.user_id != user.id:
        raise HTTPException(status_code=403, detail="Không có quyền cập nhật thông báo này.")
    notification.is_read = True
    db.commit()


def mark_all_notifications_read(db: Session, user: User) -> None:
    db.execute(
        update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    db.commit()


def scan_task_deadline_notifications(
    db: Session,
    *,
    now: datetime | None = None,
) -> None:
    current_time = now or datetime.now()
    reminder_cutoff = current_time + TASK_DEADLINE_REMINDER_WINDOW
    assignments = db.execute(
        select(
            Task.id,
            Task.title,
            Task.deadline,
            Student.user_id,
        )
        .join(TaskAssignment, TaskAssignment.task_id == Task.id)
        .join(Student, Student.id == TaskAssignment.student_id)
        .where(
            Task.deadline <= reminder_cutoff,
            Task.status.not_in((TaskStatus.DONE, TaskStatus.CANCELLED)),
        )
    ).all()
    if not assignments:
        return

    pending: list[Notification] = []
    event_keys: set[tuple[int, str]] = set()
    for task_id, title, deadline, user_id in assignments:
        is_overdue = deadline < current_time
        notification_type = (
            f"TASK_OVERDUE:{task_id}"
            if is_overdue
            else f"TASK_DUE_SOON:{task_id}"
        )
        event_keys.add((user_id, notification_type))

    existing = set(
        db.execute(
            select(Notification.user_id, Notification.notification_type).where(
                Notification.user_id.in_({user_id for user_id, _ in event_keys}),
                Notification.notification_type.in_(
                    {notification_type for _, notification_type in event_keys}
                ),
            )
        ).all()
    )

    for task_id, title, deadline, user_id in assignments:
        is_overdue = deadline < current_time
        notification_type = (
            f"TASK_OVERDUE:{task_id}"
            if is_overdue
            else f"TASK_DUE_SOON:{task_id}"
        )
        event_key = (user_id, notification_type)
        if event_key in existing:
            continue

        deadline_text = deadline.strftime("%d/%m/%Y %H:%M")
        if is_overdue:
            notification_title = "Nhiệm vụ quá hạn"
            content = (
                f"Nhiệm vụ “{title}” đã quá hạn. "
                f"Thời hạn hoàn thành: {deadline_text}."
            )
        else:
            notification_title = "Nhiệm vụ sắp đến hạn"
            content = (
                f"Nhiệm vụ “{title}” sắp đến hạn. "
                f"Thời hạn hoàn thành: {deadline_text}."
            )
        pending.append(
            Notification(
                user_id=user_id,
                title=notification_title,
                content=content,
                notification_type=notification_type,
            )
        )
        existing.add(event_key)

    if pending:
        db.add_all(pending)
        db.commit()


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