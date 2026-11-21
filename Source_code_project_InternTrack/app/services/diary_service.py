from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.diary_review import DiaryReview, DiaryReviewStatus
from app.models.internship_diary import InternshipDiary, DiaryStatus
from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole


def _lecturer_id(db: Session, user: User) -> int | None:
    return db.scalar(select(Lecturer.id).where(Lecturer.user_id == user.id))


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


def list_diaries(db: Session, user: User) -> list[dict]:
    statement = select(InternshipDiary)
    if user.role == UserRole.ADMIN:
        pass
    elif user.role == UserRole.SUPERVISOR:
        lecturer_id = _lecturer_id(db, user)
        statement = (
            statement.join(TeamMember, TeamMember.student_id == InternshipDiary.student_id)
            .join(Team, Team.id == TeamMember.team_id)
            .where(Team.supervisor_id == lecturer_id)
        )
    else:
        student_id = db.scalar(select(Student.id).where(Student.user_id == user.id))
        statement = statement.where(InternshipDiary.student_id == student_id)

    diaries = db.scalars(statement.order_by(InternshipDiary.work_date.desc())).unique().all()
    result = []
    for diary in diaries:
        student = db.get(Student, diary.student_id)
        owner = db.get(User, student.user_id) if student else None
        result.append({
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
        })
    return result


def review_diary(db: Session, diary_id: int, data, user: User) -> dict:
    diary = db.get(InternshipDiary, diary_id)
    if diary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhật ký.")
    _can_review(db, diary, user)
    status_value = DiaryReviewStatus(data.status)
    diary.status = DiaryStatus.REVIEWED if status_value == DiaryReviewStatus.REVIEWED else DiaryStatus.DRAFT
    db.add(DiaryReview(
        diary_id=diary.id,
        reviewer_id=user.id,
        content=data.content,
        status=status_value,
    ))
    db.commit()
    db.refresh(diary)
    return {"message": "Đã cập nhật nhận xét nhật ký.", "status": status_value.value, "diary_id": diary.id}