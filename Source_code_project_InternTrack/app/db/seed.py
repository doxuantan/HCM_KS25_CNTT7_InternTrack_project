"""
Seed dữ liệu mẫu cho InternTrack.

Chạy từ thư mục gốc project:
    python -m app.db.seed

Có thể chạy nhiều lần: script kiểm tra dữ liệu đã có trước khi thêm.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models import (
    EvaluationCriteria,
    InternshipPeriod,
    Lecturer,
    Student,
    Team,
    TeamMember,
)
from app.models.internship_period import PeriodStatus
from app.models.team import TeamStatus


PERIOD_NAME = "Kỳ thực tập mẫu 2026-2027"

# SRS nêu tên 6 tiêu chí, không quy định trọng số.
# Seed mẫu đặt trọng số bằng nhau (1.00) cho mỗi tiêu chí.
CRITERIA = [
    {
        "name": "Thái độ làm việc",
        "description": "Đánh giá thái độ nghiêm túc, đúng giờ và tinh thần học hỏi.",
        "weight": Decimal("1.00"),
    },
    {
        "name": "Tinh thần trách nhiệm",
        "description": "Đánh giá trách nhiệm với nhiệm vụ và cam kết được giao.",
        "weight": Decimal("1.00"),
    },
    {
        "name": "Khả năng chuyên môn",
        "description": "Đánh giá kiến thức chuyên môn và khả năng áp dụng vào công việc.",
        "weight": Decimal("1.00"),
    },
    {
        "name": "Khả năng làm việc nhóm",
        "description": "Đánh giá khả năng phối hợp, trao đổi và hỗ trợ các thành viên.",
        "weight": Decimal("1.00"),
    },
    {
        "name": "Mức độ hoàn thành công việc",
        "description": "Đánh giá chất lượng và mức độ hoàn thành nhiệm vụ đúng hạn.",
        "weight": Decimal("1.00"),
    },
    {
        "name": "Tính chủ động",
        "description": "Đánh giá khả năng tự giác, đề xuất giải pháp và chủ động xử lý công việc.",
        "weight": Decimal("1.00"),
    },
]


def seed_period(db: Session) -> InternshipPeriod:
    period = db.scalar(
        select(InternshipPeriod).where(InternshipPeriod.name == PERIOD_NAME)
    )

    if period:
        print(f"[ĐÃ CÓ] Kỳ thực tập: {period.name} (ID={period.id})")
        return period

    period = InternshipPeriod(
        name=PERIOD_NAME,
        description="Kỳ thực tập mẫu dùng để kiểm thử hệ thống InternTrack.",
        start_date=date(2026, 11, 16),
        end_date=date(2027, 2, 28),
        report_deadline=datetime(2027, 3, 7, 23, 59),
        status=PeriodStatus.UPCOMING,
    )
    db.add(period)
    db.flush()
    print(f"[TẠO MỚI] Kỳ thực tập: {period.name} (ID={period.id})")
    return period


def seed_criteria(db: Session) -> None:
    created_count = 0

    for item in CRITERIA:
        criteria = db.scalar(
            select(EvaluationCriteria).where(
                EvaluationCriteria.name == item["name"]
            )
        )

        if criteria:
            print(f"[ĐÃ CÓ] Tiêu chí: {item['name']}")
            continue

        db.add(
            EvaluationCriteria(
                name=item["name"],
                description=item["description"],
                weight=item["weight"],
                is_active=True,
            )
        )
        created_count += 1
        print(f"[TẠO MỚI] Tiêu chí: {item['name']}")

    print(f"Tổng tiêu chí được thêm mới: {created_count}/6")


def seed_teams_and_members(db: Session, period: InternshipPeriod) -> None:
    lecturers = db.scalars(select(Lecturer).order_by(Lecturer.id)).all()
    students = db.scalars(select(Student).order_by(Student.id)).all()

    if not lecturers:
        print("[BỎ QUA] Chưa có giảng viên trong bảng lecturers.")
        print("Hãy tạo tài khoản giảng viên và bản ghi lecturer trước.")
        return

    if not students:
        print("[BỎ QUA] Chưa có sinh viên trong bảng students.")
        print("Hãy tạo tài khoản sinh viên và bản ghi student trước.")
        return

    # BR04: một sinh viên không thuộc hai nhóm trong cùng một kỳ thực tập.
    assigned_student_ids = set(
        db.scalars(
            select(TeamMember.student_id)
            .join(Team, Team.id == TeamMember.team_id)
            .where(Team.period_id == period.id)
        ).all()
    )

    available_students = [
        student for student in students
        if student.id not in assigned_student_ids
    ]

    teams = db.scalars(
        select(Team).where(Team.period_id == period.id).order_by(Team.id)
    ).all()

    # Đếm thành viên hiện tại để không xếp quá 4 sinh viên vào một nhóm.
    team_counts = {}
    for team in teams:
        team_counts[team.id] = len(
            db.scalars(
                select(TeamMember.id).where(TeamMember.team_id == team.id)
            ).all()
        )

    next_team_number = len(teams) + 1
    supervisor = lecturers[0]

    for student in available_students:
        target_team = None
        for team in teams:
            if team_counts[team.id] < 4:
                target_team = team
                break

        if target_team is None:
            team_code = f"IT{period.id:03d}-{next_team_number:02d}"
            target_team = Team(
                period_id=period.id,
                supervisor_id=supervisor.id,
                team_name=f"Nhóm thực tập {next_team_number:02d}",
                team_code=team_code,
                description=f"Nhóm mẫu thuộc {period.name}.",
                status=TeamStatus.ACTIVE,
            )
            db.add(target_team)
            db.flush()
            teams.append(target_team)
            team_counts[target_team.id] = 0
            print(f"[TẠO MỚI] {target_team.team_name} ({target_team.team_code})")
            next_team_number += 1

        # Thành viên đầu tiên của nhóm được đánh dấu là nhóm trưởng.
        is_leader = (team_counts[target_team.id] == 0)
        db.add(
            TeamMember(
                team_id=target_team.id,
                student_id=student.id,
                is_leader=is_leader,
            )
        )
        team_counts[target_team.id] += 1

        print(
            f"[THÊM] Student ID={student.id} vào {target_team.team_code}"
            + (" - Nhóm trưởng" if is_leader else "")
        )

    if not available_students:
        print("[ĐÃ CÓ] Sinh viên hiện tại đã được xếp nhóm trong kỳ này.")


def main() -> None:
    db = SessionLocal()

    try:
        period = seed_period(db)
        seed_criteria(db)
        seed_teams_and_members(db, period)
        db.commit()
        print("\nSeed dữ liệu mẫu hoàn tất!")
    except Exception as error:
        db.rollback()
        print(f"Seed thất bại, đã rollback dữ liệu: {error}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
