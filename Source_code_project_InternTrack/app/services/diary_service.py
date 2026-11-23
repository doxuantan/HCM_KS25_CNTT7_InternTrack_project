from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.diary_review import DiaryReview, DiaryReviewStatus
from app.models.internship_diary import InternshipDiary, DiaryStatus
from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole


def _lecturer_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Lecturer.id).where(Lecturer.user_id == user.id))


def _student_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Student.id).where(Student.user_id == user.id))


def _can_review(db: Session, diary: InternshipDiary, user: User) -> None:
    if user.role == UserRole.ADMIN:
        return
    if user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        allowed = db.scalar(
            select(TeamMember.id)
            .join(Team, Team.id == TeamMember.team_id)
            .where(
                TeamMember.student_id == diary.student_id,
                Team.supervisor_id == lecturer_id,
            )
            .limit(1)
        )
        if allowed is not None:
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xem hoặc duyệt nhật ký này.")


def _can_view(db: Session, diary: InternshipDiary, user: User) -> None:
    if user.role == UserRole.STUDENT and _student_id(db, user) == diary.student_id:
        return
    _can_review(db, diary, user)


def _validate_task_scope(
    db: Session,
    task_id: int | None,
    student_id: int,
) -> None:
    if task_id is None:
        return
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhiệm vụ liên quan.")
    is_member = db.scalar(
        select(TeamMember.id).where(
            TeamMember.team_id == task.team_id,
            TeamMember.student_id == student_id,
        )
    )
    is_assigned = db.scalar(
        select(TaskAssignment.id).where(
            TaskAssignment.task_id == task_id,
            TaskAssignment.student_id == student_id,
        )
    )
    if is_member is None and is_assigned is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nhiệm vụ không thuộc phạm vi của bạn.")


def _diary_data(db: Session, diary: InternshipDiary) -> dict:
    student = db.get(Student, diary.student_id)
    owner = db.get(User, student.user_id) if student else None
    return {
        "id": diary.id,
        "student_id": diary.student_id,
        "task_id": diary.task_id,
        "work_date": diary.work_date,
        "work_content": diary.work_content,
        "result": diary.result,
        "difficulties": diary.difficulties,
        "lessons_learned": diary.lessons_learned,
        "status": diary.status.value,
        "created_at": diary.created_at,
        "student_name": owner.full_name if owner else None,
        "student_code": student.student_code if student else None,
        "reviews": [
            {
                "id": review.id,
                "reviewer_id": review.reviewer_id,
                "content": review.content,
                "status": review.status.value,
                "created_at": review.created_at,
            }
            for review in diary.reviews
        ],
    }


def list_diaries(
    db: Session,
    user: User,
    *,
    student_id: int | None = None,
    work_date: date | None = None,
    status_filter: DiaryStatus | None = None,
) -> list[dict]:
    statement = select(InternshipDiary).options(
        selectinload(InternshipDiary.reviews),
        selectinload(InternshipDiary.student).selectinload(Student.user),
    )
    if user.role == UserRole.ADMIN:
        pass
    elif user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        statement = (
            statement.join(TeamMember, TeamMember.student_id == InternshipDiary.student_id)
            .join(Team, Team.id == TeamMember.team_id)
            .where(Team.supervisor_id == lecturer_id)
        )
    elif user.role == UserRole.STUDENT:
        own_student_id = _student_id(db, user)
        statement = statement.where(InternshipDiary.student_id == own_student_id) if own_student_id else statement.where(False)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xem nhật ký.")

    if student_id is not None:
        statement = statement.where(InternshipDiary.student_id == student_id)
    if work_date is not None:
        statement = statement.where(InternshipDiary.work_date == work_date)
    if status_filter is not None:
        statement = statement.where(InternshipDiary.status == status_filter)

    diaries = db.scalars(
        statement.order_by(InternshipDiary.work_date.desc(), InternshipDiary.id.desc())
    ).unique().all()
    return [_diary_data(db, diary) for diary in diaries]


def create_diary(db: Session, data, user: User) -> dict:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ sinh viên có thể tạo nhật ký.")
    student_id = _student_id(db, user)
    if student_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tài khoản chưa có hồ sơ sinh viên.")
    _validate_task_scope(db, data.task_id, student_id)
    diary = InternshipDiary(
        student_id=student_id,
        task_id=data.task_id,
        work_date=data.work_date,
        work_content=data.work_content.strip(),
        result=data.result.strip() if data.result else None,
        difficulties=data.difficulties.strip() if data.difficulties else None,
        lessons_learned=data.lessons_learned.strip() if data.lessons_learned else None,
        status=DiaryStatus.SUBMITTED,
    )
    db.add(diary)
    db.commit()
    diary = db.scalar(
        select(InternshipDiary)
        .options(selectinload(InternshipDiary.reviews))
        .where(InternshipDiary.id == diary.id)
    )
    return _diary_data(db, diary)


def update_diary(db: Session, diary_id: int, data, user: User) -> dict:
    diary = db.get(InternshipDiary, diary_id)
    if diary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhật ký.")
    if user.role != UserRole.STUDENT or _student_id(db, user) != diary.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền chỉnh sửa nhật ký này.")
    if diary.status != DiaryStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chỉ có thể chỉnh sửa nhật ký nháp hoặc được yêu cầu sửa.")
    _validate_task_scope(db, data.task_id, diary.student_id)
    diary.task_id = data.task_id
    diary.work_date = data.work_date
    diary.work_content = data.work_content.strip()
    diary.result = data.result.strip() if data.result else None
    diary.difficulties = data.difficulties.strip() if data.difficulties else None
    diary.lessons_learned = data.lessons_learned.strip() if data.lessons_learned else None
    diary.status = DiaryStatus.SUBMITTED
    db.commit()
    diary = db.scalar(
        select(InternshipDiary)
        .options(selectinload(InternshipDiary.reviews))
        .where(InternshipDiary.id == diary.id)
    )
    return _diary_data(db, diary)


def get_diary_reviews(db: Session, diary_id: int, user: User) -> list[dict]:
    diary = db.scalar(
        select(InternshipDiary)
        .options(selectinload(InternshipDiary.reviews))
        .where(InternshipDiary.id == diary_id)
    )
    if diary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhật ký.")
    _can_view(db, diary, user)
    return _diary_data(db, diary)["reviews"]


def review_diary(db: Session, diary_id: int, data, user: User) -> dict:
    diary = db.get(InternshipDiary, diary_id)
    if diary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhật ký.")
    _can_review(db, diary, user)
    if diary.status != DiaryStatus.SUBMITTED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chỉ có thể nhận xét nhật ký đã nộp.")
    status_value = DiaryReviewStatus(data.status)
    diary.status = DiaryStatus.REVIEWED if status_value == DiaryReviewStatus.REVIEWED else DiaryStatus.DRAFT
    db.add(DiaryReview(
        diary_id=diary.id,
        reviewer_id=user.id,
        content=data.content.strip(),
        status=status_value,
    ))
    db.commit()
    db.refresh(diary)
    return {"message": "Đã cập nhật nhận xét nhật ký.", "status": status_value.value, "diary_id": diary.id}
