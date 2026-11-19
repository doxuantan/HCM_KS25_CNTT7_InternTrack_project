import unittest
from datetime import date, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.api.v1.router import router
from app.core.api_responses import install_api_response_handling
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.models.internship_period import InternshipPeriod, PeriodStatus
from app.models.lecturer import Lecturer
from app.models.notification import Notification
from app.models.student import Student
from app.models.task import Task, TaskPriority, TaskStatus, TaskType
from app.models.team import Team, TeamStatus
from app.models.team_member import TeamMember
from app.models.user import User, UserRole


class ScheduleNotificationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

        with self.session_factory() as db:
            supervisor = self._create_user(db, "supervisor", UserRole.SUPERVISOR)
            student = self._create_user(db, "student", UserRole.STUDENT)
            other_supervisor = self._create_user(db, "other", UserRole.SUPERVISOR)
            lecturer = Lecturer(user_id=supervisor.id, lecturer_code="L-SCH")
            other_lecturer = Lecturer(user_id=other_supervisor.id, lecturer_code="L-OTH")
            student_profile = Student(user_id=student.id, student_code="S-SCH")
            period = InternshipPeriod(
                name="Schedule period",
                start_date=date.today(),
                end_date=date.today() + timedelta(days=30),
                status=PeriodStatus.ACTIVE,
            )
            db.add_all([lecturer, other_lecturer, student_profile, period])
            db.flush()
            team = Team(
                period_id=period.id,
                supervisor_id=lecturer.id,
                team_name="Schedule team",
                team_code="SCH-01",
                status=TeamStatus.ACTIVE,
            )
            db.add(team)
            db.flush()
            db.add(TeamMember(team_id=team.id, student_id=student_profile.id))
            db.commit()

            self.supervisor_id = supervisor.id
            self.student_id = student.id
            self.other_supervisor_id = other_supervisor.id
            self.student_profile_id = student_profile.id
            self.team_id = team.id

        self.app = FastAPI()
        install_api_response_handling(self.app)
        self.app.include_router(router)

        def override_get_db():
            with self.session_factory() as db:
                yield db

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.supervisor_token = create_access_token({"sub": str(self.supervisor_id)})
        self.student_token = create_access_token({"sub": str(self.student_id)})
        self.other_token = create_access_token({"sub": str(self.other_supervisor_id)})

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    @staticmethod
    def _create_user(db, name: str, role: UserRole) -> User:
        user = User(
            email=f"{name}@schedule.test",
            password_hash="not-used",
            full_name=name,
            role=role,
            is_active=True,
        )
        db.add(user)
        db.flush()
        return user

    def _headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def test_schedule_crud_and_validation(self) -> None:
        start = datetime.now() + timedelta(hours=1)
        end = start + timedelta(hours=1)
        payload = {
            "team_id": self.team_id,
            "title": "Weekly meeting",
            "description": "Project sync",
            "location": "Room 1",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }

        created = self.client.post(
            "/api/v1/schedules",
            json=payload,
            headers=self._headers(self.supervisor_token),
        )
        self.assertEqual(created.status_code, 201, created.text)
        schedule_id = created.json()["data"]["id"]

        detail = self.client.get(
            f"/api/v1/schedules/{schedule_id}",
            headers=self._headers(self.supervisor_token),
        )
        self.assertEqual(detail.status_code, 200, detail.text)

        updated = self.client.put(
            f"/api/v1/schedules/{schedule_id}",
            json={"title": "Updated meeting", "location": "Room 2"},
            headers=self._headers(self.supervisor_token),
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["data"]["title"], "Updated meeting")

        invalid = self.client.put(
            f"/api/v1/schedules/{schedule_id}",
            json={"start_time": end.isoformat(), "end_time": start.isoformat()},
            headers=self._headers(self.supervisor_token),
        )
        self.assertEqual(invalid.status_code, 422, invalid.text)

        deleted = self.client.delete(
            f"/api/v1/schedules/{schedule_id}",
            headers=self._headers(self.supervisor_token),
        )
        self.assertEqual(deleted.status_code, 204, deleted.text)
        missing = self.client.get(
            f"/api/v1/schedules/{schedule_id}",
            headers=self._headers(self.supervisor_token),
        )
        self.assertEqual(missing.status_code, 404, missing.text)

    def test_schedule_permissions_and_meeting_notification(self) -> None:
        start = datetime.now() + timedelta(hours=2)
        end = start + timedelta(hours=1)
        payload = {
            "team_id": self.team_id,
            "title": "Sprint meeting",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }
        denied = self.client.post(
            "/api/v1/schedules",
            json=payload,
            headers=self._headers(self.other_token),
        )
        self.assertEqual(denied.status_code, 403, denied.text)

        created = self.client.post(
            "/api/v1/schedules",
            json=payload,
            headers=self._headers(self.supervisor_token),
        )
        self.assertEqual(created.status_code, 201, created.text)

        with self.session_factory() as db:
            notifications = db.query(Notification).filter_by(
                user_id=self.student_id,
                notification_type="SCHEDULE_CREATED",
            ).all()
            self.assertEqual(len(notifications), 1)
            self.assertIn("Sprint meeting", notifications[0].content)

    def test_task_assignment_notification_and_duplicate_failure(self) -> None:
        with self.session_factory() as db:
            task = Task(
                team_id=self.team_id,
                title="API implementation",
                description="Implement endpoint",
                task_type=TaskType.TEAM,
                priority=TaskPriority.HIGH,
                status=TaskStatus.TODO,
                start_date=date.today(),
                deadline=datetime.now() + timedelta(days=2),
                created_by=self.supervisor_id,
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            task_id = task.id

        assigned = self.client.put(
            f"/api/v1/tasks/{task_id}/assign",
            json={"student_id": self.student_profile_id},
            headers=self._headers(self.supervisor_token),
        )
        self.assertEqual(assigned.status_code, 200, assigned.text)

        with self.session_factory() as db:
            notifications = db.query(Notification).filter_by(
                user_id=self.student_id,
                notification_type="TASK_ASSIGNED",
            ).all()
            self.assertEqual(len(notifications), 1)
            self.assertIn("API implementation", notifications[0].content)

        duplicate = self.client.put(
            f"/api/v1/tasks/{task_id}/assign",
            json={"student_id": self.student_profile_id},
            headers=self._headers(self.supervisor_token),
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)

        with self.session_factory() as db:
            notifications = db.query(Notification).filter_by(
                user_id=self.student_id,
                notification_type="TASK_ASSIGNED",
            ).all()
            self.assertEqual(len(notifications), 1)


if __name__ == "__main__":
    unittest.main()
