import asyncio
import io
import tempfile
import unittest
import zipfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers

import app.models
from app.core.config import settings
from app.db.database import Base
from app.dependencies.auth import get_current_user
from app.models.attachment import Attachment
from app.models.internship_period import InternshipPeriod, PeriodStatus
from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.task import Task, TaskPriority, TaskStatus, TaskType
from app.models.team import Team, TeamStatus
from app.models.team_member import TeamMember
from app.models.user import User, UserRole
from app.services.attachment_service import (
    delete_attachment,
    get_attachment_file,
    upload_attachment,
)


class AttachmentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIs(app.models.Attachment, Attachment)
        self.storage = tempfile.TemporaryDirectory()
        self.previous_storage_dir = settings.ATTACHMENT_STORAGE_DIR
        self.previous_max_size = settings.MAX_ATTACHMENT_SIZE_MB
        settings.ATTACHMENT_STORAGE_DIR = Path(self.storage.name)
        settings.MAX_ATTACHMENT_SIZE_MB = 10

        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine, expire_on_commit=False)()

        self.admin = self._create_user("admin", UserRole.ADMIN)
        self.supervisor_user = self._create_user("supervisor", UserRole.SUPERVISOR)
        self.other_supervisor_user = self._create_user(
            "other-supervisor",
            UserRole.SUPERVISOR,
        )
        self.student_user = self._create_user("student", UserRole.STUDENT)
        self.other_student_user = self._create_user("other-student", UserRole.STUDENT)
        self.outsider_user = self._create_user("outsider", UserRole.STUDENT)
        self.session.flush()

        supervisor = Lecturer(
            user_id=self.supervisor_user.id,
            lecturer_code="L-01",
        )
        other_supervisor = Lecturer(
            user_id=self.other_supervisor_user.id,
            lecturer_code="L-02",
        )
        self.student = Student(
            user_id=self.student_user.id,
            student_code="S-01",
        )
        other_student = Student(
            user_id=self.other_student_user.id,
            student_code="S-02",
        )
        outsider = Student(
            user_id=self.outsider_user.id,
            student_code="S-03",
        )
        period = InternshipPeriod(
            name="Test period",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status=PeriodStatus.ACTIVE,
        )
        self.session.add_all(
            [
                supervisor,
                other_supervisor,
                self.student,
                other_student,
                outsider,
                period,
            ]
        )
        self.session.flush()

        team = Team(
            period_id=period.id,
            supervisor_id=supervisor.id,
            team_name="Test team",
            team_code="T-01",
            status=TeamStatus.ACTIVE,
        )
        self.session.add(team)
        self.session.flush()
        self.task = Task(
            team_id=team.id,
            title="Test task",
            task_type=TaskType.TEAM,
            priority=TaskPriority.LOW,
            status=TaskStatus.TODO,
            start_date=date(2026, 1, 1),
            deadline=datetime(2026, 12, 31),
            created_by=self.supervisor_user.id,
        )
        self.session.add_all(
            [
                self.task,
                TeamMember(team_id=team.id, student_id=self.student.id),
                TeamMember(team_id=team.id, student_id=other_student.id),
            ]
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        settings.ATTACHMENT_STORAGE_DIR = self.previous_storage_dir
        settings.MAX_ATTACHMENT_SIZE_MB = self.previous_max_size
        self.storage.cleanup()

    def _create_user(self, name: str, role: UserRole) -> User:
        user = User(
            email=f"{name}@example.test",
            password_hash="not-used",
            full_name=name,
            role=role,
            is_active=True,
        )
        self.session.add(user)
        return user

    def _upload(
        self,
        content: bytes,
        filename: str = "report.pdf",
        content_type: str = "application/pdf",
    ) -> Attachment:
        upload = UploadFile(
            filename=filename,
            file=io.BytesIO(content),
            headers=Headers({"content-type": content_type}),
        )
        return asyncio.run(
            upload_attachment(
                db=self.session,
                current_user=self.student_user,
                file=upload,
                task_id=self.task.id,
                diary_id=None,
                report_id=None,
            )
        )

    def test_upload_download_and_delete_owned_file(self) -> None:
        attachment = self._upload(b"%\n%PDF-1.7\nvalid test file", "report #1.pdf")
        self.assertEqual(attachment.file_name, "report #1.pdf")
        self.assertEqual(attachment.mime_type, "application/pdf")
        self.assertEqual(attachment.file_size, len(b"%\n%PDF-1.7\nvalid test file"))

        record = self.session.get(Attachment, attachment.id)
        self.assertIsNotNone(record)
        self.assertNotEqual(record.stored_filename, record.file_name)
        stored_path = Path(settings.attachment_storage_path) / record.stored_filename
        self.assertTrue(stored_path.is_file())
        file_record, file_path = get_attachment_file(
            db=self.session,
            attachment_id=attachment.id,
            current_user=self.student_user,
        )
        self.assertEqual(file_record.id, attachment.id)
        self.assertEqual(file_path.read_bytes(), b"%\n%PDF-1.7\nvalid test file")

        delete_attachment(
            db=self.session,
            attachment_id=attachment.id,
            current_user=self.student_user,
        )
        self.assertIsNone(self.session.get(Attachment, attachment.id))
        self.assertFalse(file_path.exists())

    def test_rejects_spoofed_content_and_cleans_temporary_file(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            self._upload(b"not a PDF")
        self.assertEqual(raised.exception.status_code, 415)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(Attachment)), 0)
        self.assertEqual(list(Path(settings.attachment_storage_path).iterdir()), [])

    def test_rejects_mime_type_mismatch(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            self._upload(b"%PDF-1.7\nvalid test file", content_type="image/png")
        self.assertEqual(raised.exception.status_code, 415)
        self.assertEqual(list(Path(settings.attachment_storage_path).iterdir()), [])

    def test_accepts_docx_and_png_signatures(self) -> None:
        docx_content = io.BytesIO()
        with zipfile.ZipFile(docx_content, "w") as archive:
            archive.writestr("word/document.xml", "<document/>")
        docx = self._upload(
            docx_content.getvalue(),
            "resume.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        png = self._upload(
            b"\x89PNG\r\n\x1a\nimage-data",
            "photo.png",
            "image/png",
        )
        self.assertEqual(docx.mime_type, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertEqual(png.mime_type, "image/png")

    def test_enforces_size_limit_during_streaming(self) -> None:
        max_size = settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
        with self.assertRaises(HTTPException) as raised:
            self._upload(b"%PDF-" + b"x" * max_size)
        self.assertEqual(raised.exception.status_code, 413)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(Attachment)), 0)
        self.assertEqual(list(Path(settings.attachment_storage_path).iterdir()), [])

    def test_scope_and_admin_permissions(self) -> None:
        attachment = self._upload(b"%PDF-1.7\nvalid test file")
        get_attachment_file(
            db=self.session,
            attachment_id=attachment.id,
            current_user=self.other_student_user,
        )
        get_attachment_file(
            db=self.session,
            attachment_id=attachment.id,
            current_user=self.supervisor_user,
        )

        with self.assertRaises(HTTPException) as denied_outsider:
            get_attachment_file(
                db=self.session,
                attachment_id=attachment.id,
                current_user=self.outsider_user,
            )
        self.assertEqual(denied_outsider.exception.status_code, 403)

        with self.assertRaises(HTTPException) as denied_supervisor:
            get_attachment_file(
                db=self.session,
                attachment_id=attachment.id,
                current_user=self.other_supervisor_user,
            )
        self.assertEqual(denied_supervisor.exception.status_code, 403)

        with self.assertRaises(HTTPException) as denied_delete:
            delete_attachment(
                db=self.session,
                attachment_id=attachment.id,
                current_user=self.other_student_user,
            )
        self.assertEqual(denied_delete.exception.status_code, 403)

        _, file_path = get_attachment_file(
            db=self.session,
            attachment_id=attachment.id,
            current_user=self.admin,
        )
        self.assertTrue(file_path.is_file())
        delete_attachment(
            db=self.session,
            attachment_id=attachment.id,
            current_user=self.admin,
        )
        self.assertFalse(file_path.exists())

    def test_delete_handles_missing_physical_file(self) -> None:
        attachment = self._upload(b"%PDF-1.7\nvalid test file")
        record = self.session.get(Attachment, attachment.id)
        self.assertIsNotNone(record)
        file_path = Path(settings.attachment_storage_path) / record.stored_filename
        file_path.unlink()

        delete_attachment(
            db=self.session,
            attachment_id=attachment.id,
            current_user=self.student_user,
        )
        self.assertIsNone(self.session.get(Attachment, attachment.id))

    def test_delete_database_failure_restores_file(self) -> None:
        attachment = self._upload(b"%PDF-1.7\nvalid test file")
        record = self.session.get(Attachment, attachment.id)
        self.assertIsNotNone(record)
        file_path = Path(settings.attachment_storage_path) / record.stored_filename

        with patch.object(self.session, "commit", side_effect=SQLAlchemyError):
            with self.assertRaises(HTTPException) as raised:
                delete_attachment(
                    db=self.session,
                    attachment_id=attachment.id,
                    current_user=self.student_user,
                )
        self.assertEqual(raised.exception.status_code, 500)
        self.assertIsNotNone(self.session.get(Attachment, attachment.id))
        self.assertTrue(file_path.is_file())

    def test_path_traversal_metadata_is_never_followed_or_deleted(self) -> None:
        attachment = self._upload(b"%PDF-1.7\nvalid test file")
        record = self.session.get(Attachment, attachment.id)
        self.assertIsNotNone(record)
        record.stored_filename = "..\\outside.pdf"
        self.session.commit()

        with self.assertRaises(HTTPException) as denied_get:
            get_attachment_file(
                db=self.session,
                attachment_id=attachment.id,
                current_user=self.student_user,
            )
        self.assertEqual(denied_get.exception.status_code, 404)
        with self.assertRaises(HTTPException) as denied_delete:
            delete_attachment(
                db=self.session,
                attachment_id=attachment.id,
                current_user=self.student_user,
            )
        self.assertEqual(denied_delete.exception.status_code, 409)
        self.assertIsNotNone(self.session.get(Attachment, attachment.id))

    def test_database_failure_removes_saved_file(self) -> None:
        with patch.object(self.session, "commit", side_effect=SQLAlchemyError):
            with self.assertRaises(HTTPException) as raised:
                self._upload(b"%PDF-1.7\nvalid test file")
        self.assertEqual(raised.exception.status_code, 500)
        self.assertEqual(self.session.scalar(select(func.count()).select_from(Attachment)), 0)
        self.assertEqual(list(Path(settings.attachment_storage_path).iterdir()), [])

    def test_get_unknown_attachment_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            get_attachment_file(
                db=self.session,
                attachment_id=999,
                current_user=self.admin,
            )
        self.assertEqual(raised.exception.status_code, 404)

    def test_authentication_dependency_rejects_missing_credentials(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            get_current_user(credentials=None, db=self.session)
        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
