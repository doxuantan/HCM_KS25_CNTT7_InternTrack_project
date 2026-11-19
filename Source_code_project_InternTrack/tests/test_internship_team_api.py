import unittest
from datetime import date

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
from app.models.team import Team, TeamStatus
from app.models.team_member import TeamMember
from app.models.user import User, UserRole


class InternshipAndTeamApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

        with self.session_factory() as db:
            self.admin = self._create_user(db, "admin", UserRole.ADMIN)
            self.supervisor = self._create_user(db, "supervisor", UserRole.SUPERVISOR)
            self.other_supervisor = self._create_user(
                db,
                "other-supervisor",
                UserRole.SUPERVISOR,
            )
            self.student = self._create_user(db, "student", UserRole.STUDENT)
            self.outsider = self._create_user(db, "outsider", UserRole.STUDENT)
            self.lecturer = Lecturer(
                user_id=self.supervisor.id,
                lecturer_code="L-01",
            )
            self.other_lecturer = Lecturer(
                user_id=self.other_supervisor.id,
                lecturer_code="L-02",
            )
            self.student_profile = Student(
                user_id=self.student.id,
                student_code="S-01",
            )
            self.outsider_profile = Student(
                user_id=self.outsider.id,
                student_code="S-02",
            )
            self.period = InternshipPeriod(
                name="Test period",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                status=PeriodStatus.UPCOMING,
            )
            db.add_all(
                [
                    self.lecturer,
                    self.other_lecturer,
                    self.student_profile,
                    self.outsider_profile,
                    self.period,
                ]
            )
            db.flush()
            self.team = Team(
                period_id=self.period.id,
                supervisor_id=self.lecturer.id,
                team_name="Supervisor team",
                team_code="SUP-01",
                status=TeamStatus.ACTIVE,
            )
            self.other_team = Team(
                period_id=self.period.id,
                supervisor_id=self.other_lecturer.id,
                team_name="Other team",
                team_code="SUP-02",
                status=TeamStatus.ACTIVE,
            )
            db.add_all([self.team, self.other_team])
            db.flush()
            db.add(TeamMember(team_id=self.team.id, student_id=self.student_profile.id))
            db.commit()
            self.admin_id = self.admin.id
            self.supervisor_id = self.supervisor.id
            self.other_supervisor_id = self.other_supervisor.id
            self.student_id = self.student.id
            self.outsider_id = self.outsider.id
            self.period_id = self.period.id
            self.team_id = self.team.id
            self.other_team_id = self.other_team.id
            self.lecturer_id = self.lecturer.id
            self.other_lecturer_id = self.other_lecturer.id
            self.student_profile_id = self.student_profile.id
            self.outsider_profile_id = self.outsider_profile.id

        self.tokens = {
            "admin": self._token(self.admin_id),
            "supervisor": self._token(self.supervisor_id),
            "other_supervisor": self._token(self.other_supervisor_id),
            "student": self._token(self.student_id),
            "outsider": self._token(self.outsider_id),
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

    def test_internship_crud_status_validation_and_roles(self) -> None:
        self.assertEqual(
            self.client.get("/api/v1/internship-periods").status_code,
            401,
        )
        readable = self.client.get(
            "/api/v1/internship-periods",
            headers=self._auth("student"),
        )
        self.assertEqual(readable.status_code, 200, readable.text)
        self.assertEqual(len(readable.json()["data"]), 1)

        payload = {
            "name": "New period",
            "start_date": "2027-01-01",
            "end_date": "2027-06-30",
            "status": "UPCOMING",
        }
        denied = self.client.post(
            "/api/v1/internship-periods",
            json=payload,
            headers=self._auth("student"),
        )
        self.assertEqual(denied.status_code, 403, denied.text)

        created = self.client.post(
            "/api/v1/internship-periods",
            json=payload,
            headers=self._auth("admin"),
        )
        self.assertEqual(created.status_code, 201, created.text)
        period_id = created.json()["data"]["id"]

        invalid = self.client.put(
            f"/api/v1/internship-periods/{period_id}",
            json={**payload, "start_date": "2027-07-01"},
            headers=self._auth("admin"),
        )
        self.assertEqual(invalid.status_code, 400, invalid.text)

        updated = self.client.put(
            f"/api/v1/internship-periods/{period_id}",
            json={**payload, "name": "Updated period"},
            headers=self._auth("admin"),
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["data"]["name"], "Updated period")

        status_response = self.client.patch(
            f"/api/v1/internship-periods/{period_id}/status",
            json={"status": "ACTIVE"},
            headers=self._auth("admin"),
        )
        self.assertEqual(status_response.status_code, 200, status_response.text)
        self.assertEqual(status_response.json()["data"]["status"], "ACTIVE")

        invalid_status = self.client.patch(
            f"/api/v1/internship-periods/{period_id}/status",
            json={"status": "INVALID"},
            headers=self._auth("admin"),
        )
        self.assertEqual(invalid_status.status_code, 422, invalid_status.text)

        deleted = self.client.delete(
            f"/api/v1/internship-periods/{period_id}",
            headers=self._auth("admin"),
        )
        self.assertEqual(deleted.status_code, 204, deleted.text)

    def test_team_crud_and_role_scoping(self) -> None:
        student_teams = self.client.get(
            "/api/v1/teams",
            headers=self._auth("student"),
        )
        self.assertEqual(student_teams.status_code, 200, student_teams.text)
        self.assertEqual(
            [team["id"] for team in student_teams.json()["data"]],
            [self.team_id],
        )

        hidden_team = self.client.get(
            f"/api/v1/teams/{self.other_team_id}",
            headers=self._auth("student"),
        )
        self.assertEqual(hidden_team.status_code, 404, hidden_team.text)

        supervisor_teams = self.client.get(
            "/api/v1/teams",
            headers=self._auth("supervisor"),
        )
        self.assertEqual(supervisor_teams.status_code, 200, supervisor_teams.text)
        self.assertEqual(
            [team["id"] for team in supervisor_teams.json()["data"]],
            [self.team_id],
        )
        denied_update = self.client.put(
            f"/api/v1/teams/{self.other_team_id}",
            json={"team_name": "Unauthorized"},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(denied_update.status_code, 404, denied_update.text)

        create_payload = {
            "period_id": self.period_id,
            "team_name": "Created by supervisor",
            "team_code": "SUP-03",
            "description": "Owned by current supervisor",
        }
        created = self.client.post(
            "/api/v1/teams",
            json=create_payload,
            headers=self._auth("supervisor"),
        )
        self.assertEqual(created.status_code, 201, created.text)
        created_data = created.json()["data"]
        self.assertEqual(created_data["supervisor_id"], self.lecturer_id)

        updated = self.client.put(
            f"/api/v1/teams/{created_data['id']}",
            json={"team_name": "Renamed team", "description": None},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["data"]["team_name"], "Renamed team")
        self.assertIsNone(updated.json()["data"]["description"])

        duplicate_code = self.client.post(
            "/api/v1/teams",
            json={**create_payload, "team_code": "SUP-01"},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(duplicate_code.status_code, 409, duplicate_code.text)

        student_create = self.client.post(
            "/api/v1/teams",
            json=create_payload,
            headers=self._auth("student"),
        )
        self.assertEqual(student_create.status_code, 403, student_create.text)

        admin_teams = self.client.get(
            "/api/v1/teams",
            headers=self._auth("admin"),
        )
        self.assertEqual(admin_teams.status_code, 200, admin_teams.text)
        self.assertEqual(len(admin_teams.json()["data"]), 3)

        admin_created = self.client.post(
            "/api/v1/teams",
            json={
                **create_payload,
                "supervisor_id": self.other_lecturer.id,
                "team_code": "ADM-01",
                "team_name": "Created by admin",
            },
            headers=self._auth("admin"),
        )
        self.assertEqual(admin_created.status_code, 201, admin_created.text)
        self.assertEqual(
            admin_created.json()["data"]["supervisor_id"],
            self.other_lecturer.id,
        )

        admin_updated = self.client.put(
            f"/api/v1/teams/{self.other_team_id}",
            json={"team_name": "Admin updated team"},
            headers=self._auth("admin"),
        )
        self.assertEqual(admin_updated.status_code, 200, admin_updated.text)
        self.assertEqual(
            admin_updated.json()["data"]["team_name"],
            "Admin updated team",
        )

    def test_team_member_leader_and_supervisor_management(self) -> None:
        change_leader = self.client.patch(
            f"/api/v1/teams/{self.team_id}/leader",
            json={"student_id": self.student_profile_id},
            headers=self._auth("admin"),
        )
        self.assertEqual(change_leader.status_code, 200, change_leader.text)
        self.assertTrue(change_leader.json()["data"]["is_leader"])

        denied_leader_change = self.client.patch(
            f"/api/v1/teams/{self.team_id}/leader",
            json={"student_id": self.outsider_profile_id},
            headers=self._auth("supervisor"),
        )
        self.assertEqual(denied_leader_change.status_code, 403, denied_leader_change.text)

        add_member = self.client.post(
            f"/api/v1/teams/{self.team_id}/members",
            json={"student_id": self.outsider_profile_id},
            headers=self._auth("student"),
        )
        self.assertEqual(add_member.status_code, 201, add_member.text)

        member_list = self.client.get(
            f"/api/v1/teams/{self.team_id}/members",
            headers=self._auth("student"),
        )
        self.assertEqual(member_list.status_code, 200, member_list.text)
        self.assertEqual(len(member_list.json()["data"]), 2)

        br05 = self.client.post(
            f"/api/v1/teams/{self.other_team_id}/members",
            json={"student_id": self.outsider_profile_id},
            headers=self._auth("admin"),
        )
        self.assertEqual(br05.status_code, 409, br05.text)
        self.assertIn("BR05", br05.json()["message"])

        remove_member = self.client.delete(
            f"/api/v1/teams/{self.team_id}/members/{self.outsider_profile_id}",
            headers=self._auth("student"),
        )
        self.assertEqual(remove_member.status_code, 204, remove_member.text)

        remove_leader = self.client.delete(
            f"/api/v1/teams/{self.team_id}/members/{self.student_profile_id}",
            headers=self._auth("admin"),
        )
        self.assertEqual(remove_leader.status_code, 409, remove_leader.text)

        change_supervisor = self.client.patch(
            f"/api/v1/teams/{self.team_id}/supervisor",
            json={"supervisor_id": self.other_lecturer_id},
            headers=self._auth("admin"),
        )
        self.assertEqual(change_supervisor.status_code, 200, change_supervisor.text)

        invalid_supervisor = self.client.patch(
            f"/api/v1/teams/{self.team_id}/supervisor",
            json={"supervisor_id": 9999},
            headers=self._auth("admin"),
        )
        self.assertEqual(invalid_supervisor.status_code, 404, invalid_supervisor.text)

    def test_team_validation_and_not_found(self) -> None:
        missing_reference = self.client.post(
            "/api/v1/teams",
            json={
                "period_id": 9999,
                "supervisor_id": self.lecturer_id,
                "team_name": "Invalid period",
                "team_code": "NEW-01",
            },
            headers=self._auth("admin"),
        )
        self.assertEqual(missing_reference.status_code, 404, missing_reference.text)

        blank_name = self.client.post(
            "/api/v1/teams",
            json={
                "period_id": self.period_id,
                "supervisor_id": self.lecturer_id,
                "team_name": "   ",
                "team_code": "NEW-01",
            },
            headers=self._auth("admin"),
        )
        self.assertEqual(blank_name.status_code, 422, blank_name.text)

        missing_team = self.client.get(
            "/api/v1/teams/9999",
            headers=self._auth("admin"),
        )
        self.assertEqual(missing_team.status_code, 404, missing_team.text)


if __name__ == "__main__":
    unittest.main()
