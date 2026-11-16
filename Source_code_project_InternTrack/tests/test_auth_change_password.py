import asyncio
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from sqlalchemy import create_engine, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.auth import router as auth_router
from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import get_db
from app.models.user import User, UserRole


class ChangePasswordApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        User.__table__.create(bind=cls.engine)
        cls.session_factory = sessionmaker(bind=cls.engine)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    def setUp(self) -> None:
        self.db = self.session_factory()
        self.user = User(
            email=f"password-test-{uuid4().hex}@example.com",
            password_hash=hash_password("old-password"),
            full_name="Password Test",
            role=UserRole.STUDENT,
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        self.app = FastAPI()
        self.app.include_router(auth_router, prefix="/api/v1")

        def override_get_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_get_db

    def tearDown(self) -> None:
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def request(
        self,
        method: str,
        body: dict[str, str] | None = None,
        token: str | None = None,
    ) -> tuple[int, dict]:
        headers = [(b"content-type", b"application/json")]
        if token is not None:
            headers.append((b"authorization", f"Bearer {token}".encode("ascii")))

        request_body = json.dumps(body or {}).encode("utf-8")
        messages = []
        received = False

        async def receive():
            nonlocal received
            if received:
                return {"type": "http.disconnect"}
            received = True
            return {
                "type": "http.request",
                "body": request_body,
                "more_body": False,
            }

        async def send(message):
            messages.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": "/api/v1/auth/change-password",
            "raw_path": b"/api/v1/auth/change-password",
            "query_string": b"",
            "headers": headers,
            "server": ("testserver", 80),
            "client": ("testclient", 123),
            "root_path": "",
        }
        asyncio.run(self.app(scope, receive, send))
        response = next(message for message in messages if message["type"] == "http.response.start")
        response_body = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        return response["status"], json.loads(response_body)

    def token(self) -> str:
        return create_access_token({"sub": str(self.user.id)})

    def test_requires_authentication(self) -> None:
        status_code, _ = self.request(
            "PUT",
            {"current_password": "old-password", "new_password": "new-password"},
        )

        self.assertEqual(status_code, 401)

    def test_changes_password_without_exposing_hash(self) -> None:
        status_code, response = self.request(
            "PUT",
            {"current_password": "old-password", "new_password": "new-password"},
            self.token(),
        )

        self.db.refresh(self.user)
        self.assertEqual(status_code, 200)
        self.assertEqual(response, {"message": "Password changed successfully."})
        self.assertTrue(verify_password("new-password", self.user.password_hash))
        self.assertFalse(verify_password("old-password", self.user.password_hash))
        self.assertNotIn("password", response)
        self.assertNotIn("password_hash", response)

    def test_rejects_wrong_current_password(self) -> None:
        status_code, _ = self.request(
            "PUT",
            {"current_password": "incorrect", "new_password": "new-password"},
            self.token(),
        )

        self.assertEqual(status_code, 400)
        self.assertTrue(verify_password("old-password", self.user.password_hash))

    def test_request_cannot_target_another_user(self) -> None:
        other_user = User(
            email=f"other-password-test-{uuid4().hex}@example.com",
            password_hash=hash_password("other-password"),
            full_name="Other User",
            role=UserRole.STUDENT,
            is_active=True,
        )
        self.db.add(other_user)
        self.db.commit()
        self.db.refresh(other_user)

        status_code, _ = self.request(
            "PUT",
            {
                "current_password": "old-password",
                "new_password": "new-password",
                "user_id": str(other_user.id),
            },
            self.token(),
        )

        self.db.refresh(other_user)
        self.assertEqual(status_code, 422)
        self.assertTrue(verify_password("other-password", other_user.password_hash))
        self.db.execute(delete(User).where(User.id == other_user.id))
        self.db.commit()

    def test_validates_password_length_and_bcrypt_byte_limit(self) -> None:
        for password in ("short", "é" * 37):
            with self.subTest(password_length=len(password.encode("utf-8"))):
                status_code, _ = self.request(
                    "PUT",
                    {"current_password": "old-password", "new_password": password},
                    self.token(),
                )
                self.assertEqual(status_code, 422)

    def test_accepts_password_at_bcrypt_byte_limit(self) -> None:
        password = "é" * 36
        status_code, _ = self.request(
            "PUT",
            {"current_password": "old-password", "new_password": password},
            self.token(),
        )

        self.assertEqual(status_code, 200)
        self.db.refresh(self.user)
        self.assertTrue(verify_password(password, self.user.password_hash))

    def test_rolls_back_if_database_commit_fails(self) -> None:
        with patch.object(self.db, "commit", side_effect=SQLAlchemyError("commit failed")):
            status_code, _ = self.request(
                "PUT",
                {"current_password": "old-password", "new_password": "new-password"},
                self.token(),
            )

        self.assertEqual(status_code, 500)
        self.db.refresh(self.user)
        self.assertTrue(verify_password("old-password", self.user.password_hash))

    def test_openapi_documents_change_password_endpoint(self) -> None:
        paths = self.app.openapi()["paths"]
        operation = paths["/api/v1/auth/change-password"]["put"]

        self.assertIn("requestBody", operation)
        self.assertIn("400", operation["responses"])
        self.assertIn("401", operation["responses"])
        self.assertIn("422", operation["responses"])
        self.assertTrue(operation["security"])
        self.assertIn("/api/v1/auth/login", paths)
        self.assertIn("/api/v1/auth/register", paths)
        self.assertIn("/api/v1/auth/logout", paths)
