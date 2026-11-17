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
from app.models.task import Task, TaskStatus
from app.models.task_assignment import TaskAssignment
from app.models.team import Team, TeamStatus
from app.models.team_member import TeamMember
from app.models.user import User, UserRole


class TaskApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

        with self.session_factory() as db:
            admin = self._create_user(db, "admin", UserRole.ADMIN)
            supervisor = self._create_user(db, "supervisor", UserRole.SUPERVISOR)
            other_supervisor = self._create_user(
                db,
                "other-supervisor",
                UserRole.SUPERVISOR,
            )
            student = self._create_user(db, "student", UserRole.STUDENT)
            outsider = self._create_user(db, "outsider", UserRole.STUDENT)
            inactive = self._create_user(db, "inactive", UserRole.STUDENT)
            inactive.is_active = False

            lecturer = Lecturer(user_id=supervisor.id, lecturer_code="L-01")
            other_lecturer = Lecturer(
                user_id=other_supervisor.id,
                lecturer_code="L-02",
            )
            student_profile = Student(user_id=student.id, student_code="S-01")
            outsider_profile = Student(user_id=outsider.id, student_code="S-02")
            inactive_profile = Student(user_id=inactive.id, student_code="S-03")
            period = InternshipPeriod(
                name="Task test period",
                start_date=date.today(),
                end_date=date.today() + timedelta(days=60),
                status=PeriodStatus.ACTIVE,
            )
            db.add_all(
                [
                    lecturer,
                    other_lecturer,
                    student_profile,
                    outsider_profile,
                    inactive_profile,
                    period,
                ]
            )
            db.flush()
            team = Team(
                period_id=period.id,
                supervisor_id=lecturer.id,
                team_name="Task team",
                team_code="TASK-01",
                status=TeamStatus.ACTIVE,
            )
            other_team = Team(
                period_id=period.id,
                supervisor_id=other_lecturer.id,
                team_name="Other task team",
                team_code="TASK-02",
                status=TeamStatus.ACTIVE,
            )
            db.add_all([team, other_team])
            db.flush()
            db.add(TeamMember(team_id=team.id, student_id=student_profile.id))
            db.commit()

            self.admin_id = admin.id
            self.supervisor_id = supervisor.id
            self.other_supervisor_id = other_supervisor.id
            self.student_id = student.id
            self.student_profile_id = student_profile.id
            self.outsider_profile_id = outsider_profile.id
            self.inactive_profile_id = inactive_profile.id
            self.team_id = team.id
            self.other_team_id = other_team.id

        self.tokens = {
            "admin": self._token(self.admin_id),
            "supervisor": self._token(self.supervisor_id),
            "other_supervisor": self._token(self.other_supervisor_id),
            "student": self._token(self.student_id),
            "outsider": self._token(self._user_id("outsider")),
        }
        self.app = FastAPI()
        install_api_response_handling(self.app)
        self.app.include_router(router)

        def override_get_db():
            with self.session_factory() as db:
                yield db

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    @staticmethod
    def _create_user(db, name: str, role: UserRole) -> User:
        user = User(
            email=f"{name}@example.test",
            password_hash="not-used",
            full_name=name,
            role=role,
            is_active=True,
        )
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def _token(user_id: int) -> str:
        return create_access_token({"sub": str(user_id)})

    def _auth(self, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[role]}"}

    def _user_id(self, name: str) -> int:
        with self.session_factory() as db:
            return db.query(User.id).filter_by(email=f"{name}@example.test").scalar()

    def _task_payload(self, **overrides) -> dict:
        payload = {
            "team_id": self.team_id,
            "title": "Deliver task API",
            "description": "Complete the task work",
            "task_type": "TEAM",
            "priority": "MEDIUM",
            "start_date": (date.today() + timedelta(days=1)).isoformat(),
            "deadline": (datetime.now() + timedelta(days=5)).isoformat(),
        }
        payload.update(overrides)
        return payload

    def _create_task(self, role: str = "supervisor", **overrides) -> int:
        response = self.client.post(
            "/api/v1/tasks",
            json=self._task_payload(**overrides),
            headers=self._auth(role),
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["data"]["id"]

    def _assign_student(self, task_id: int) -> None:
        response = self.client.put(
            f"/api/v1/tasks/{task_id}/assign",
            json={"student_id": self.student_profile_id},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_create_team_and_personal_tasks(self) -> None:
        team_task = self.client.post(
            "/api/v1/tasks",
            json=self._task_payload(task_type="TEAM"),
            headers=self._auth("supervisor"),
        )
        self.assertEqual(team_task.status_code, 201, team_task.text)
        self.assertEqual(team_task.json()["data"]["task_type"], "TEAM")
        self.assertEqual(team_task.json()["data"]["status"], "TODO")

        personal_task = self.client.post(
            "/api/v1/tasks",
            json=self._task_payload(task_type="PERSONAL", title="Personal work"),
            headers=self._auth("admin"),
        )
        self.assertEqual(personal_task.status_code, 201, personal_task.text)
        self.assertEqual(personal_task.json()["data"]["task_type"], "PERSONAL")

    def test_create_task_rejects_invalid_deadline_payload_and_permissions(self) -> None:
        past_deadline = self.client.post(
            "/api/v1/tasks",
            json=self._task_payload(
                deadline=(datetime.now() - timedelta(days=1)).isoformat()
            ),
            headers=self._auth("supervisor"),
        )
        self.assertEqual(past_deadline.status_code, 422, past_deadline.text)

        before_start = self.client.post(
            "/api/v1/tasks",
            json=self._task_payload(
                start_date=(date.today() + timedelta(days=10)).isoformat(),
                deadline=(datetime.now() + timedelta(days=2)).isoformat(),
            ),
            headers=self._auth("supervisor"),
        )
        self.assertEqual(before_start.status_code, 422, before_start.text)

        missing_fields = self.client.post(
            "/api/v1/tasks",
            json={"team_id": self.team_id},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(missing_fields.status_code, 422, missing_fields.text)

        missing_team = self.client.post(
            "/api/v1/tasks",
            json=self._task_payload(team_id=9999),
            headers=self._auth("admin"),
        )
        self.assertEqual(missing_team.status_code, 404, missing_team.text)

        denied = self.client.post(
            "/api/v1/tasks",
            json=self._task_payload(),
            headers=self._auth("student"),
        )
        self.assertEqual(denied.status_code, 403, denied.text)

        wrong_supervisor = self.client.post(
            "/api/v1/tasks",
            json=self._task_payload(team_id=self.other_team_id),
            headers=self._auth("supervisor"),
        )
        self.assertEqual(wrong_supervisor.status_code, 403, wrong_supervisor.text)

    def test_assign_task_checks_task_member_account_and_permission(self) -> None:
        task_id = self._create_task()
        assigned = self.client.put(
            f"/api/v1/tasks/{task_id}/assign",
            json={"student_id": self.student_profile_id},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(assigned.status_code, 200, assigned.text)
        self.assertEqual(
            assigned.json()["data"]["assignments"][0]["student_id"],
            self.student_profile_id,
        )

        missing_task = self.client.put(
            "/api/v1/tasks/9999/assign",
            json={"student_id": self.student_profile_id},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(missing_task.status_code, 404, missing_task.text)

        missing_student = self.client.put(
            f"/api/v1/tasks/{task_id}/assign",
            json={"student_id": 9999},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(missing_student.status_code, 404, missing_student.text)

        nonmember = self.client.put(
            f"/api/v1/tasks/{task_id}/assign",
            json={"student_id": self.outsider_profile_id},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(nonmember.status_code, 422, nonmember.text)

        inactive = self.client.put(
            f"/api/v1/tasks/{task_id}/assign",
            json={"student_id": self.inactive_profile_id},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(inactive.status_code, 422, inactive.text)

        denied = self.client.put(
            f"/api/v1/tasks/{task_id}/assign",
            json={"student_id": self.student_profile_id},
            headers=self._auth("student"),
        )
        self.assertEqual(denied.status_code, 403, denied.text)

    def test_status_only_allows_todo_to_done(self) -> None:
        task_id = self._create_task()
        invalid = self.client.patch(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "IN_PROGRESS"},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(invalid.status_code, 409, invalid.text)

        completed = self.client.patch(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "DONE"},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertEqual(completed.json()["data"]["status"], "DONE")

        repeated_transition = self.client.patch(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "DONE"},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(repeated_transition.status_code, 409, repeated_transition.text)

        unauthorized = self.client.patch(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "DONE"},
            headers=self._auth("other_supervisor"),
        )
        self.assertEqual(unauthorized.status_code, 403, unauthorized.text)

        missing = self.client.patch(
            "/api/v1/tasks/9999/status",
            json={"status": "DONE"},
            headers=self._auth("admin"),
        )
        self.assertEqual(missing.status_code, 404, missing.text)

        invalid_enum = self.client.patch(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "INVALID"},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(invalid_enum.status_code, 422, invalid_enum.text)

    def test_progress_bounds_and_assignment_permissions(self) -> None:
        task_id = self._create_task()
        unassigned = self.client.patch(
            f"/api/v1/tasks/{task_id}/progress",
            json={"progress": 50},
            headers=self._auth("outsider"),
        )
        self.assertEqual(unassigned.status_code, 403, unassigned.text)

        self._assign_student(task_id)

        for value in (0, 100):
            updated = self.client.patch(
                f"/api/v1/tasks/{task_id}/progress",
                json={"progress": value},
                headers=self._auth("student"),
            )
            self.assertEqual(updated.status_code, 200, updated.text)
            self.assertEqual(updated.json()["data"]["progress"], value)

        for value in (-1, 101):
            invalid = self.client.patch(
                f"/api/v1/tasks/{task_id}/progress",
                json={"progress": value},
                headers=self._auth("student"),
            )
            self.assertEqual(invalid.status_code, 422, invalid.text)

        unassigned = self.client.patch(
            f"/api/v1/tasks/{task_id}/progress",
            json={"progress": 50},
            headers=self._auth("other_supervisor"),
        )
        self.assertEqual(unassigned.status_code, 403, unassigned.text)

        missing = self.client.patch(
            "/api/v1/tasks/9999/progress",
            json={"progress": 50},
            headers=self._auth("student"),
        )
        self.assertEqual(missing.status_code, 404, missing.text)

        with self.session_factory() as db:
            assignment = db.query(TaskAssignment).filter_by(task_id=task_id).one()
            self.assertEqual(assignment.progress, 100)
            task = db.get(Task, task_id)
            self.assertEqual(task.status, TaskStatus.TODO)


if __name__ == "__main__":
    unittest.main()
