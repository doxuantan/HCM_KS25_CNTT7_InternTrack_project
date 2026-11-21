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
from app.models.student import Student
from app.models.task import Task, TaskPriority, TaskStatus, TaskType
from app.models.task_assignment import AssignmentStatus, TaskAssignment
from app.models.team import Team, TeamStatus
from app.models.team_member import TeamMember
from app.models.user import User, UserRole


class ProgressApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

        with self.session_factory() as db:
            admin = User(email="admin@example.test", password_hash="x", full_name="Admin", role=UserRole.ADMIN)
            supervisor = User(email="supervisor@example.test", password_hash="x", full_name="Supervisor", role=UserRole.SUPERVISOR)
            student = User(email="student@example.test", password_hash="x", full_name="Student", role=UserRole.STUDENT)
            leader = User(email="leader@example.test", password_hash="x", full_name="Leader", role=UserRole.STUDENT)
            db.add_all([admin, supervisor, student, leader])
            db.flush()

            lecturer = Lecturer(user_id=supervisor.id, lecturer_code="GV01")
            student_profile = Student(user_id=student.id, student_code="SV01")
            leader_profile = Student(user_id=leader.id, student_code="SV02")
            period = InternshipPeriod(
                name="Period",
                start_date=date.today(),
                end_date=date.today() + timedelta(days=30),
                status=PeriodStatus.ACTIVE,
            )
            db.add_all([lecturer, student_profile, leader_profile, period])
            db.flush()

            team = Team(
                period_id=period.id,
                supervisor_id=lecturer.id,
                team_name="Team A",
                team_code="TEAM-A",
                status=TeamStatus.ACTIVE,
            )
            db.add(team)
            db.flush()
            db.add_all([
                TeamMember(team_id=team.id, student_id=student_profile.id, is_leader=False),
                TeamMember(team_id=team.id, student_id=leader_profile.id, is_leader=True),
            ])

            done = Task(
                team_id=team.id,
                title="Done task",
                task_type=TaskType.PERSONAL,
                priority=TaskPriority.MEDIUM,
                status=TaskStatus.DONE,
                start_date=date.today(),
                deadline=datetime.now() + timedelta(days=3),
                created_by=supervisor.id,
            )
            overdue = Task(
                team_id=team.id,
                title="Overdue task",
                task_type=TaskType.PERSONAL,
                priority=TaskPriority.HIGH,
                status=TaskStatus.IN_PROGRESS,
                start_date=date.today() - timedelta(days=5),
                deadline=datetime.now() - timedelta(days=1),
                created_by=supervisor.id,
            )
            cancelled = Task(
                team_id=team.id,
                title="Cancelled task",
                task_type=TaskType.PERSONAL,
                priority=TaskPriority.LOW,
                status=TaskStatus.CANCELLED,
                start_date=date.today(),
                deadline=datetime.now() + timedelta(days=1),
                created_by=supervisor.id,
            )
            db.add_all([done, overdue, cancelled])
            db.flush()
            db.add_all([
                TaskAssignment(task_id=done.id, student_id=student_profile.id, assigned_by=supervisor.id, progress=100, status=AssignmentStatus.DONE),
                TaskAssignment(task_id=overdue.id, student_id=student_profile.id, assigned_by=supervisor.id, progress=40, status=AssignmentStatus.IN_PROGRESS),
                TaskAssignment(task_id=cancelled.id, student_id=student_profile.id, assigned_by=supervisor.id, progress=0, status=AssignmentStatus.TODO),
            ])
            db.commit()

            self.admin_id = admin.id
            self.supervisor_id = supervisor.id
            self.student_id = student.id
            self.student_profile_id = student_profile.id
            self.leader_id = leader.id
            self.team_id = team.id

        self.tokens = {
            "admin": create_access_token({"sub": str(self.admin_id)}),
            "supervisor": create_access_token({"sub": str(self.supervisor_id)}),
            "student": create_access_token({"sub": str(self.student_id)}),
            "leader": create_access_token({"sub": str(self.leader_id)}),
        }
        self.app = FastAPI()
        install_api_response_handling(self.app)
        self.app.include_router(router)
        self.app.dependency_overrides[get_db] = self._override_db
        self.client = TestClient(self.app, raise_server_exceptions=False)

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

    def test_personal_team_and_overview_progress(self) -> None:
        me = self.client.get("/api/v1/progress/me", headers=self._auth("student"))
        self.assertEqual(me.status_code, 200, me.text)
        data = me.json()["data"]
        self.assertEqual(data["total_tasks"], 2)
        self.assertEqual(data["completed_tasks"], 1)
        self.assertEqual(data["overdue_tasks"], 1)
        self.assertEqual(data["progress"], 50.0)

        team = self.client.get(f"/api/v1/progress/team/{self.team_id}", headers=self._auth("leader"))
        self.assertEqual(team.status_code, 200, team.text)
        team_data = team.json()["data"]
        self.assertEqual(team_data["total_tasks"], 2)
        self.assertEqual(team_data["progress"], 50.0)
        self.assertEqual(len(team_data["members"]), 2)

        overview = self.client.get("/api/v1/progress/overview", headers=self._auth("supervisor"))
        self.assertEqual(overview.status_code, 200, overview.text)
        overview_data = overview.json()["data"]
        self.assertEqual(overview_data["total_tasks"], 2)
        self.assertEqual(overview_data["completed_tasks"], 1)

    def test_member_permissions_empty_data_and_cancelled_task(self) -> None:
        member = self.client.get(
            f"/api/v1/progress/member/{self.student_profile_id}",
            headers=self._auth("supervisor"),
        )
        self.assertEqual(member.status_code, 200, member.text)
        self.assertEqual(member.json()["data"]["total_tasks"], 2)

        denied = self.client.get(
            f"/api/v1/progress/member/{self.student_profile_id}",
            headers=self._auth("leader"),
        )
        self.assertEqual(denied.status_code, 200, denied.text)

        missing_team = self.client.get(
            "/api/v1/progress/team/9999",
            headers=self._auth("admin"),
        )
        self.assertEqual(missing_team.status_code, 404, missing_team.text)


if __name__ == "__main__":
    unittest.main()
