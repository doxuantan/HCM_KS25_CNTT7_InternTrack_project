import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.api.v1.router import router
from app.core.api_responses import install_api_response_handling
from app.core.config import Settings, settings
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.seed import seed_demo_records
from app.models.diary_review import DiaryReview
from app.models.evaluation_criteria import EvaluationCriteria
from app.models.evaluation import Evaluation
from app.models.internship_period import InternshipPeriod, PeriodStatus
from app.models.lecturer import Lecturer
from app.models.internship_diary import InternshipDiary
from app.models.report import Report
from app.models.student import Student
from app.models.team import Team, TeamStatus
from app.models.team_member import TeamMember
from app.models.user import User, UserRole


class DiaryReportEvaluationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = tempfile.TemporaryDirectory()
        self.previous_storage_dir = settings.ATTACHMENT_STORAGE_DIR
        settings.ATTACHMENT_STORAGE_DIR = Path(self.storage.name)
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

        with self.session_factory() as db:
            admin = self._user(db, "admin", UserRole.ADMIN)
            supervisor = self._user(db, "supervisor", UserRole.SUPERVISOR)
            other_supervisor = self._user(db, "other-supervisor", UserRole.SUPERVISOR)
            student = self._user(db, "student", UserRole.STUDENT)
            outsider = self._user(db, "outsider", UserRole.STUDENT)
            db.flush()
            lecturer = Lecturer(user_id=supervisor.id, lecturer_code="L-01")
            other_lecturer = Lecturer(user_id=other_supervisor.id, lecturer_code="L-02")
            student_profile = Student(user_id=student.id, student_code="S-01")
            outsider_profile = Student(user_id=outsider.id, student_code="S-02")
            period = InternshipPeriod(
                name="Test period",
                start_date=date.today() - timedelta(days=1),
                end_date=date.today() + timedelta(days=30),
                status=PeriodStatus.ACTIVE,
            )
            criteria = EvaluationCriteria(name="Quality", weight=1)
            db.add_all([lecturer, other_lecturer, student_profile, outsider_profile, period, criteria])
            db.flush()
            team = Team(
                period_id=period.id,
                supervisor_id=lecturer.id,
                team_name="Team A",
                team_code="TEAM-A",
                status=TeamStatus.ACTIVE,
            )
            other_team = Team(
                period_id=period.id,
                supervisor_id=other_lecturer.id,
                team_name="Team B",
                team_code="TEAM-B",
                status=TeamStatus.ACTIVE,
            )
            db.add_all([team, other_team])
            db.flush()
            db.add(TeamMember(team_id=team.id, student_id=student_profile.id, is_leader=True))
            db.add(TeamMember(team_id=other_team.id, student_id=outsider_profile.id))
            db.commit()
            self.ids = {
                "admin": admin.id,
                "supervisor": supervisor.id,
                "other_supervisor": other_supervisor.id,
                "student": student.id,
                "student_profile": student_profile.id,
                "outsider": outsider.id,
                "outsider_profile": outsider_profile.id,
                "period": period.id,
                "team": team.id,
                "other_team": other_team.id,
                "criteria": criteria.id,
            }

        self.tokens = {
            role: create_access_token({"sub": str(user_id)})
            for role, user_id in self.ids.items()
            if role in {"admin", "supervisor", "other_supervisor", "student", "outsider"}
        }
        self.app = FastAPI()
        install_api_response_handling(self.app)
        self.app.include_router(router)
        self.app.dependency_overrides[get_db] = self._override_db
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _user(self, db, name: str, role: UserRole) -> User:
        user = User(
            email=f"{name}@example.test",
            password_hash="unused",
            full_name=name,
            role=role,
            is_active=True,
        )
        db.add(user)
        return user

    def _override_db(self):
        with self.session_factory() as db:
            yield db

    def _auth(self, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[role]}"}

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        settings.ATTACHMENT_STORAGE_DIR = self.previous_storage_dir
        self.storage.cleanup()

    def test_diary_create_filters_reviews_and_scope(self) -> None:
        created = self.client.post(
            "/api/v1/diaries",
            headers=self._auth("student"),
            json={
                "work_date": date.today().isoformat(),
                "work_content": "Implemented API endpoint",
                "result": "Endpoint is ready",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        diary = created.json()["data"]
        self.assertEqual(diary["status"], "SUBMITTED")

        filtered = self.client.get(
            f"/api/v1/diaries?student_id={self.ids['student_profile']}&status=SUBMITTED",
            headers=self._auth("supervisor"),
        )
        self.assertEqual(filtered.status_code, 200, filtered.text)
        self.assertEqual([item["id"] for item in filtered.json()["data"]], [diary["id"]])

        review = self.client.post(
            f"/api/v1/diaries/{diary['id']}/review",
            headers=self._auth("supervisor"),
            json={"status": "REVISION_REQUIRED", "content": "Please add test details."},
        )
        self.assertEqual(review.status_code, 200, review.text)
        updated = self.client.put(
            f"/api/v1/diaries/{diary['id']}",
            headers=self._auth("student"),
            json={
                "work_date": date.today().isoformat(),
                "work_content": "Added requested test details",
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["data"]["status"], "SUBMITTED")
        reviews = self.client.get(
            f"/api/v1/diaries/{diary['id']}/review",
            headers=self._auth("student"),
        )
        self.assertEqual(reviews.status_code, 200, reviews.text)
        self.assertEqual(reviews.json()["data"][0]["content"], "Please add test details.")

        denied = self.client.get(
            f"/api/v1/diaries/{diary['id']}/review",
            headers=self._auth("outsider"),
        )
        self.assertEqual(denied.status_code, 403)

    def test_report_upload_submit_review_notification_and_approval_lock(self) -> None:
        created = self.client.post(
            "/api/v1/reports",
            headers=self._auth("student"),
            json={
                "period_id": self.ids["period"],
                "title": "Weekly report",
                "report_type": "WEEKLY",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        report_id = created.json()["data"]["id"]
        group_report = self.client.post(
            "/api/v1/reports",
            headers=self._auth("student"),
            json={
                "team_id": self.ids["team"],
                "period_id": self.ids["period"],
                "title": "Team report",
                "report_type": "FINAL",
            },
        )
        self.assertEqual(group_report.status_code, 201, group_report.text)
        self.assertEqual(group_report.json()["data"]["team_id"], self.ids["team"])

        missing_file = self.client.post(
            f"/api/v1/reports/{report_id}/submit",
            headers=self._auth("student"),
        )
        self.assertEqual(missing_file.status_code, 422)

        upload = self.client.post(
            "/api/v1/attachments/upload",
            headers=self._auth("student"),
            data={"report_id": str(report_id)},
            files={"file": ("weekly.pdf", b"%PDF-1.7\nreport contents", "application/pdf")},
        )
        self.assertEqual(upload.status_code, 201, upload.text)

        submitted = self.client.post(
            f"/api/v1/reports/{report_id}/submit",
            headers=self._auth("student"),
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        revision = self.client.post(
            f"/api/v1/reports/{report_id}/review",
            headers=self._auth("supervisor"),
            json={"status": "REVISION_REQUIRED", "content": "Please add conclusions."},
        )
        self.assertEqual(revision.status_code, 200, revision.text)
        self.assertEqual(
            self.client.get("/api/v1/notifications", headers=self._auth("student")).json()["data"][0]["notification_type"],
            f"REPORT_REVISION_REQUIRED:{report_id}",
        )
        reviews = self.client.get(
            f"/api/v1/reports/{report_id}/review",
            headers=self._auth("student"),
        )
        self.assertEqual(reviews.json()["data"][0]["content"], "Please add conclusions.")

        resubmitted = self.client.post(
            f"/api/v1/reports/{report_id}/submit",
            headers=self._auth("student"),
        )
        self.assertEqual(resubmitted.status_code, 200, resubmitted.text)
        approved = self.client.post(
            f"/api/v1/reports/{report_id}/review",
            headers=self._auth("supervisor"),
            json={"status": "APPROVED", "content": "Approved."},
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        locked = self.client.post(
            f"/api/v1/reports/{report_id}/submit",
            headers=self._auth("student"),
        )
        self.assertEqual(locked.status_code, 409)
        locked_upload = self.client.post(
            "/api/v1/attachments/upload",
            headers=self._auth("student"),
            data={"report_id": str(report_id)},
            files={"file": ("replacement.pdf", b"%PDF-1.7\nreplacement", "application/pdf")},
        )
        self.assertEqual(locked_upload.status_code, 409)

    def test_evaluation_permissions_publish_and_student_visibility(self) -> None:
        payload = {
            "student_id": self.ids["student_profile"],
            "period_id": self.ids["period"],
            "comment": "Good progress",
            "details": [
                {"criteria_id": self.ids["criteria"], "score": "8.5", "comment": "Good quality"}
            ],
        }
        denied = self.client.post(
            "/api/v1/evaluations",
            headers=self._auth("student"),
            json=payload,
        )
        self.assertEqual(denied.status_code, 403)

        created = self.client.post(
            "/api/v1/evaluations",
            headers=self._auth("supervisor"),
            json=payload,
        )
        self.assertEqual(created.status_code, 201, created.text)
        evaluation = created.json()["data"]
        self.assertEqual(Decimal(evaluation["total_score"]), Decimal("8.5"))
        self.assertEqual(evaluation["details"][0]["criteria_name"], "Quality")
        reviewer_read = self.client.get(
            f"/api/v1/evaluations/{evaluation['id']}",
            headers=self._auth("supervisor"),
        )
        self.assertEqual(reviewer_read.status_code, 200, reviewer_read.text)
        update_payload = {
            **payload,
            "details": [
                {"criteria_id": self.ids["criteria"], "score": "9.0", "comment": "Improved"}
            ],
        }
        updated = self.client.put(
            f"/api/v1/evaluations/{evaluation['id']}",
            headers=self._auth("supervisor"),
            json=update_payload,
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(Decimal(updated.json()["data"]["total_score"]), Decimal("9.0"))

        hidden = self.client.get("/api/v1/evaluations", headers=self._auth("student"))
        self.assertEqual(hidden.status_code, 200, hidden.text)
        self.assertEqual(hidden.json()["data"], [])

        published = self.client.post(
            f"/api/v1/evaluations/{evaluation['id']}/publish",
            headers=self._auth("supervisor"),
        )
        self.assertEqual(published.status_code, 200, published.text)
        published_notice = self.client.get(
            "/api/v1/notifications",
            headers=self._auth("student"),
        )
        self.assertEqual(
            published_notice.json()["data"][0]["notification_type"],
            f"EVALUATION_PUBLISHED:{evaluation['id']}",
        )
        visible = self.client.get("/api/v1/evaluations", headers=self._auth("student"))
        self.assertEqual([row["id"] for row in visible.json()["data"]], [evaluation["id"]])
        student_read = self.client.get(
            f"/api/v1/evaluations/{evaluation['id']}",
            headers=self._auth("student"),
        )
        self.assertEqual(student_read.status_code, 200, student_read.text)

        denied_publish = self.client.post(
            f"/api/v1/evaluations/{evaluation['id']}/publish",
            headers=self._auth("outsider"),
        )
        self.assertEqual(denied_publish.status_code, 403)
        update = self.client.put(
            f"/api/v1/evaluations/{evaluation['id']}",
            headers=self._auth("supervisor"),
            json=payload,
        )
        self.assertEqual(update.status_code, 409)

        deletable = self.client.post(
            "/api/v1/evaluations",
            headers=self._auth("supervisor"),
            json=payload,
        )
        self.assertEqual(deletable.status_code, 201, deletable.text)
        deleted = self.client.delete(
            f"/api/v1/evaluations/{deletable.json()['data']['id']}",
            headers=self._auth("supervisor"),
        )
        self.assertEqual(deleted.status_code, 204, deleted.text)

    def test_report_and_evaluation_scope_and_invalid_input(self) -> None:
        foreign_report = self.client.post(
            "/api/v1/reports",
            headers=self._auth("student"),
            json={
                "student_id": self.ids["outsider_profile"],
                "period_id": self.ids["period"],
                "title": "Not mine",
                "report_type": "FINAL",
            },
        )
        self.assertEqual(foreign_report.status_code, 403)

        foreign_evaluation = self.client.post(
            "/api/v1/evaluations",
            headers=self._auth("supervisor"),
            json={
                "student_id": self.ids["outsider_profile"],
                "period_id": self.ids["period"],
                "details": [],
            },
        )
        self.assertEqual(foreign_evaluation.status_code, 403)

        invalid_score = self.client.post(
            "/api/v1/evaluations",
            headers=self._auth("supervisor"),
            json={
                "student_id": self.ids["student_profile"],
                "period_id": self.ids["period"],
                "details": [{"criteria_id": self.ids["criteria"], "score": -1}],
            },
        )
        self.assertEqual(invalid_score.status_code, 422)

    def test_demo_seed_is_idempotent_and_creates_domain_records(self) -> None:
        with self.session_factory() as db:
            period = db.get(InternshipPeriod, self.ids["period"])
            seed_demo_records(db, period)
            db.commit()
            counts = [
                db.scalar(select(func.count()).select_from(model))
                for model in (InternshipDiary, DiaryReview, Report, Evaluation)
            ]

            seed_demo_records(db, period)
            db.commit()
            repeated_counts = [
                db.scalar(select(func.count()).select_from(model))
                for model in (InternshipDiary, DiaryReview, Report, Evaluation)
            ]

        self.assertEqual(repeated_counts, counts)
        self.assertEqual(counts, [2, 2, 2, 2])

    def test_cors_configuration_rejects_wildcard_and_non_origin_values(self) -> None:
        base = {
            "DATABASE_URL": "sqlite://",
            "SECRET_KEY": "test-secret-key-with-at-least-32-characters",
        }
        configured = Settings(**base, ALLOWED_ORIGINS=["http://localhost:5500"])
        self.assertEqual(configured.ALLOWED_ORIGINS, ["http://localhost:5500"])
        for origin in ("*", "https://example.test/path", "javascript://example.test"):
            with self.subTest(origin=origin):
                with self.assertRaises(ValidationError):
                    Settings(**base, ALLOWED_ORIGINS=[origin])


if __name__ == "__main__":
    unittest.main()
