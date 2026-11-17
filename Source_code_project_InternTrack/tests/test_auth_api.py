import os
import time
import unittest
from datetime import timedelta
from tempfile import NamedTemporaryFile

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.api.v1.router import router
from app.core.api_responses import install_api_response_handling
from app.core.security import create_access_token, hash_password
from app.db.database import Base, get_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import User, UserRole


class AuthApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

        with self.session_factory() as db:
            self.admin = self._create_user(
                db,
                "admin@example.test",
                "Admin_Test_123",
                UserRole.ADMIN,
            )
            self.student = self._create_user(
                db,
                "student@example.test",
                "Student_Test_123",
                UserRole.STUDENT,
            )
            self.supervisor = self._create_user(
                db,
                "supervisor@example.test",
                "Supervisor_Test_123",
                UserRole.SUPERVISOR,
            )
            self.inactive = self._create_user(
                db,
                "inactive@example.test",
                "Inactive_Test_123",
                UserRole.STUDENT,
                is_active=False,
            )
            db.commit()
            self.admin_id = self.admin.id
            self.student_id = self.student.id
            self.inactive_id = self.inactive.id

        self.binary_file = NamedTemporaryFile(suffix=".pdf", delete=False)
        self.binary_file.write(b"%PDF-1.7\nbinary response")
        self.binary_file.close()

        self.app = FastAPI()
        install_api_response_handling(self.app)
        self.app.include_router(router)

        def override_get_db():
            with self.session_factory() as db:
                yield db

        self.app.dependency_overrides[get_db] = override_get_db

        @self.app.get("/_test/database-error")
        def database_error():
            raise SQLAlchemyError("sensitive SQL details")

        @self.app.get("/_test/unhandled-error")
        def unhandled_error():
            raise RuntimeError("sensitive internal details")

        @self.app.get("/_test/binary", response_class=FileResponse)
        def binary_response():
            return FileResponse(
                self.binary_file.name,
                filename="sample.pdf",
                media_type="application/pdf",
            )

        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        os.unlink(self.binary_file.name)

    @staticmethod
    def _create_user(
        db,
        email: str,
        password: str,
        role: UserRole,
        *,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=email.split("@", 1)[0],
            role=role,
            is_active=is_active,
        )
        db.add(user)
        db.flush()
        return user

    def _assert_error(self, response, status_code: int) -> dict:
        self.assertEqual(response.status_code, status_code, response.text)
        payload = response.json()
        self.assertIs(payload["success"], False)
        self.assertIsNone(payload["data"])
        self.assertIsInstance(payload["message"], str)
        self.assertIsInstance(payload["errors"], list)
        return payload

    def _login(self, email: str, password: str) -> str:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertIsNone(payload["errors"])
        return payload["data"]["access_token"]

    def _auth(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def test_register_success_duplicate_and_sensitive_fields(self) -> None:
        body = {
            "email": "new.student@example.test",
            "password": "New_Student_123",
            "full_name": "New Student",
        }
        response = self.client.post("/api/v1/auth/register", json=body)
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertIsNone(payload["errors"])
        self.assertEqual(payload["data"]["email"], body["email"])
        self.assertEqual(payload["data"]["role"], "STUDENT")
        self.assertNotIn("password_hash", payload["data"])
        self.assertNotIn("password", payload["data"])

        duplicate = self.client.post("/api/v1/auth/register", json=body)
        self._assert_error(duplicate, 409)

    def test_register_validation_and_role_spoofing(self) -> None:
        base_body = {
            "email": "validation@example.test",
            "password": "Valid_Test_123",
            "full_name": "Validation User",
        }
        invalid_requests = (
            {**base_body, "email": "not-an-email"},
            {key: value for key, value in base_body.items() if key != "password"},
            {**base_body, "password": "short"},
            {**base_body, "password": "p" * 73},
            {**base_body, "email": 17},
            {**base_body, "role": "ADMIN"},
        )
        for body in invalid_requests:
            with self.subTest(body=body):
                response = self.client.post("/api/v1/auth/register", json=body)
                payload = self._assert_error(response, 422)
                self.assertTrue(payload["errors"])
                self.assertNotIn('"input"', response.text)
                self.assertNotIn("Valid_Test_123", response.text)
                if len(body.get("password", "")) > 72:
                    self.assertEqual(
                        payload["message"],
                        "Password must not exceed 72 UTF-8 bytes.",
                    )
                else:
                    self.assertEqual(payload["message"], "Validation failed")

    def test_login_success_invalid_credentials_and_validation(self) -> None:
        token = self._login("student@example.test", "Student_Test_123")
        self.assertTrue(token)

        self._assert_error(
            self.client.post(
                "/api/v1/auth/login",
                json={"email": "unknown@example.test", "password": "Student_Test_123"},
            ),
            401,
        )
        self._assert_error(
            self.client.post(
                "/api/v1/auth/login",
                json={"email": "student@example.test", "password": "Wrong_Password"},
            ),
            401,
        )
        for body in (
            {"email": "student@example.test"},
            {"password": "Student_Test_123"},
            {"email": "invalid", "password": "Student_Test_123"},
        ):
            with self.subTest(body=body):
                self._assert_error(
                    self.client.post("/api/v1/auth/login", json=body),
                    422,
                )

    def test_login_rejects_inactive_user(self) -> None:
        self._assert_error(
            self.client.post(
                "/api/v1/auth/login",
                json={
                    "email": "inactive@example.test",
                    "password": "Inactive_Test_123",
                },
            ),
            403,
        )

    def test_me_checks_valid_missing_malformed_expired_and_unknown_tokens(self) -> None:
        token = self._login("student@example.test", "Student_Test_123")
        response = self.client.get("/api/v1/auth/me", headers=self._auth(token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["id"], self.student_id)

        self._assert_error(self.client.get("/api/v1/auth/me"), 401)
        self._assert_error(
            self.client.get("/api/v1/auth/me", headers=self._auth("not-a-jwt")),
            401,
        )
        unknown_user_token = create_access_token({"sub": "999999"})
        self._assert_error(
            self.client.get(
                "/api/v1/auth/me",
                headers=self._auth(unknown_user_token),
            ),
            401,
        )

        expired_token = create_access_token(
            {"sub": str(self.student_id)},
            expires_delta=timedelta(seconds=1),
        )
        time.sleep(2.1)
        self._assert_error(
            self.client.get("/api/v1/auth/me", headers=self._auth(expired_token)),
            401,
        )

        inactive_token = create_access_token({"sub": str(self.inactive_id)})
        self._assert_error(
            self.client.get("/api/v1/auth/me", headers=self._auth(inactive_token)),
            403,
        )

    def test_change_password_validates_and_updates_login_credentials(self) -> None:
        token = self._login("student@example.test", "Student_Test_123")
        headers = self._auth(token)

        self._assert_error(
            self.client.put(
                "/api/v1/auth/change-password",
                headers=headers,
                json={
                    "current_password": "incorrect",
                    "new_password": "New_Student_123",
                },
            ),
            400,
        )
        self._assert_error(
            self.client.put(
                "/api/v1/auth/change-password",
                headers=headers,
                json={
                    "current_password": "Student_Test_123",
                    "new_password": "short",
                },
            ),
            422,
        )
        self._assert_error(
            self.client.put(
                "/api/v1/auth/change-password",
                headers=headers,
                json={
                    "current_password": "Student_Test_123",
                    "new_password": "New_Student_123",
                    "confirm_password": "does-not-match",
                },
            ),
            422,
        )
        self._assert_error(
            self.client.put(
                "/api/v1/auth/change-password",
                json={
                    "current_password": "Student_Test_123",
                    "new_password": "New_Student_123",
                },
            ),
            401,
        )
        inactive_token = create_access_token({"sub": str(self.inactive_id)})
        self._assert_error(
            self.client.put(
                "/api/v1/auth/change-password",
                headers=self._auth(inactive_token),
                json={
                    "current_password": "Inactive_Test_123",
                    "new_password": "New_Student_123",
                },
            ),
            403,
        )

        success = self.client.put(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": "Student_Test_123",
                "new_password": "New_Student_123",
            },
        )
        self.assertEqual(success.status_code, 200)
        self.assertTrue(success.json()["success"])
        self.assertEqual(success.json()["data"]["message"], "Password changed successfully.")
        self._assert_error(
            self.client.post(
                "/api/v1/auth/login",
                json={
                    "email": "student@example.test",
                    "password": "Student_Test_123",
                },
            ),
            401,
        )
        self._login("student@example.test", "New_Student_123")

    def test_logout_is_acknowledged_but_access_token_remains_stateless(self) -> None:
        token = self._login("student@example.test", "Student_Test_123")
        response = self.client.post("/api/v1/auth/logout", headers=self._auth(token))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIn("remains valid until it expires", response.json()["data"]["message"])
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers=self._auth(token)).status_code,
            200,
        )

    def test_role_permissions_use_database_role_and_return_401_or_403(self) -> None:
        self._assert_error(self.client.get("/api/v1/users"), 401)
        student_token = self._login("student@example.test", "Student_Test_123")
        self._assert_error(
            self.client.get("/api/v1/users", headers=self._auth(student_token)),
            403,
        )

        forged_role_token = create_access_token(
            {"sub": str(self.student_id), "role": "ADMIN"}
        )
        self._assert_error(
            self.client.get("/api/v1/users", headers=self._auth(forged_role_token)),
            403,
        )
        supervisor_token = self._login(
            "supervisor@example.test",
            "Supervisor_Test_123",
        )
        self._assert_error(
            self.client.get("/api/v1/users", headers=self._auth(supervisor_token)),
            403,
        )

        admin_token = self._login("admin@example.test", "Admin_Test_123")
        response = self.client.get("/api/v1/users", headers=self._auth(admin_token))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertIsInstance(response.json()["data"], list)

    def test_common_http_database_and_unknown_exception_responses(self) -> None:
        admin_token = self._login("admin@example.test", "Admin_Test_123")
        not_found = self.client.get(
            "/api/v1/users/999999",
            headers=self._auth(admin_token),
        )
        self._assert_error(not_found, 404)

        database_error = self.client.get("/_test/database-error")
        database_payload = self._assert_error(database_error, 500)
        self.assertNotIn("sensitive SQL details", database_error.text)
        self.assertEqual(database_payload["message"], "A database error occurred.")

        unknown_error = self.client.get("/_test/unhandled-error")
        unknown_payload = self._assert_error(unknown_error, 500)
        self.assertNotIn("sensitive internal details", unknown_error.text)
        self.assertEqual(unknown_payload["message"], "An unexpected error occurred.")

    def test_binary_and_openapi_responses_are_not_wrapped(self) -> None:
        binary = self.client.get("/_test/binary")
        self.assertEqual(binary.status_code, 200)
        self.assertEqual(binary.headers["content-type"], "application/pdf")
        self.assertEqual(binary.content, b"%PDF-1.7\nbinary response")

        openapi_response = self.client.get("/openapi.json")
        self.assertEqual(openapi_response.status_code, 200)
        openapi = openapi_response.json()
        self.assertIn("openapi", openapi)
        login_schema = openapi["paths"]["/api/v1/auth/login"]["post"]["responses"]["200"]
        response_schema = login_schema["content"]["application/json"]["schema"]
        self.assertEqual(response_schema["properties"]["success"]["const"], True)
        token_schema = response_schema["properties"]["data"]["$ref"].rsplit("/", 1)[-1]
        self.assertIn(
            "access_token",
            openapi["components"]["schemas"][token_schema]["properties"],
        )


if __name__ == "__main__":
    unittest.main()
