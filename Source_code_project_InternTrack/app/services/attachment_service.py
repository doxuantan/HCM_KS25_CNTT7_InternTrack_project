import logging
import os
import re
import tempfile
import uuid
import zipfile
from pathlib import Path, PureWindowsPath

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attachment import Attachment
from app.models.internship_diary import InternshipDiary
from app.models.lecturer import Lecturer
from app.models.report import Report, ReportStatus
from app.models.student import Student
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User, UserRole
from app.schemas.attachment import AttachmentResponse


logger = logging.getLogger(__name__)
CHUNK_SIZE = 1024 * 1024
MAX_FILENAME_LENGTH = 255

ALLOWED_TYPES = {
    ".pdf": ("application/pdf",),
    ".doc": ("application/msword",),
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    ".xls": ("application/vnd.ms-excel",),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",),
    ".ppt": ("application/vnd.ms-powerpoint",),
    ".pptx": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    ".png": ("image/png",),
    ".jpg": ("image/jpeg",),
    ".jpeg": ("image/jpeg",),
}

SAFE_STORED_NAME = re.compile(
    r"^[0-9a-f]{32}\.(pdf|doc|docx|xls|xlsx|ppt|pptx|png|jpg|jpeg)$"
)


def _http_error(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _clean_original_filename(filename: str | None) -> tuple[str, str]:
    if not filename:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "A filename is required.")

    original_name = PureWindowsPath(filename).name
    original_name = "".join(
        character for character in original_name
        if ord(character) >= 32 and ord(character) != 127
    ).strip()
    if not original_name or len(original_name) > MAX_FILENAME_LENGTH:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The filename is empty or too long.",
        )

    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_TYPES:
        raise _http_error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "This file extension is not supported.",
        )
    return original_name, extension


def _validate_declared_mime_type(content_type: str | None, extension: str) -> str:
    mime_type = (content_type or "").split(";", 1)[0].strip().lower()
    if mime_type not in ALLOWED_TYPES[extension]:
        raise _http_error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "The file MIME type does not match its supported extension.",
        )
    return mime_type


def _contains_ole_stream(path: Path, names: tuple[str, ...]) -> bool:
    markers = tuple(
        marker
        for name in names
        for marker in (name.encode("ascii"), name.encode("utf-16le"))
    )
    overlap = max(map(len, markers)) - 1
    tail = b""
    with path.open("rb") as file_handle:
        while chunk := file_handle.read(CHUNK_SIZE):
            data = tail + chunk
            if any(marker in data for marker in markers):
                return True
            tail = data[-overlap:]
    return False


def _validate_file_signature(path: Path, extension: str) -> None:
    with path.open("rb") as file_handle:
        header = file_handle.read(1024)

    if extension == ".pdf" and b"%PDF-" in header:
        return
    if extension == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
        return
    if extension in (".jpg", ".jpeg") and header.startswith(b"\xff\xd8\xff"):
        return

    if extension in (".docx", ".xlsx", ".pptx"):
        package_entry = {
            ".docx": "word/document.xml",
            ".xlsx": "xl/workbook.xml",
            ".pptx": "ppt/presentation.xml",
        }[extension]
        try:
            with zipfile.ZipFile(path) as archive:
                if package_entry in archive.namelist():
                    return
        except (OSError, zipfile.BadZipFile):
            pass

    ole_signature = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    if header.startswith(ole_signature):
        ole_streams = {
            ".doc": ("WordDocument",),
            ".xls": ("Workbook", "Book"),
            ".ppt": ("PowerPoint Document",),
        }
        if extension in ole_streams and _contains_ole_stream(path, ole_streams[extension]):
            return

    raise _http_error(
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        "The file contents do not match the declared file type.",
    )


def _assert_target_access(
    db: Session,
    current_user: User,
    *,
    task_id: int | None = None,
    diary_id: int | None = None,
    report_id: int | None = None,
) -> None:
    target_count = sum(value is not None for value in (task_id, diary_id, report_id))
    if target_count != 1:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Exactly one of task_id, diary_id, or report_id must be provided.",
        )

    if task_id is not None:
        task = db.get(Task, task_id)
        if task is None:
            raise _http_error(status.HTTP_404_NOT_FOUND, "The linked task was not found.")
        if current_user.role == UserRole.ADMIN:
            return
        if current_user.role == UserRole.SUPERVISOR:
            lecturer: Lecturer | None = current_user.lecturer
            team = db.get(Team, task.team_id)
            if lecturer is not None and team is not None and team.supervisor_id == lecturer.id:
                return
        elif current_user.role == UserRole.STUDENT:
            student: Student | None = current_user.student
            if student is not None:
                is_member = db.scalar(
                    select(TeamMember.id).where(
                        TeamMember.team_id == task.team_id,
                        TeamMember.student_id == student.id,
                    )
                )
                is_assigned = db.scalar(
                    select(TaskAssignment.id).where(
                        TaskAssignment.task_id == task.id,
                        TaskAssignment.student_id == student.id,
                    )
                )
                if is_member is not None or is_assigned is not None:
                    return
        raise _http_error(status.HTTP_403_FORBIDDEN, "You cannot access this task.")

    if diary_id is not None:
        diary = db.get(InternshipDiary, diary_id)
        if diary is None:
            raise _http_error(status.HTTP_404_NOT_FOUND, "The linked diary was not found.")
        if current_user.role == UserRole.ADMIN:
            return
        if current_user.role == UserRole.STUDENT:
            student = current_user.student
            if student is not None and diary.student_id == student.id:
                return
        elif current_user.role == UserRole.SUPERVISOR:
            lecturer = current_user.lecturer
            if lecturer is not None:
                manages_student = db.scalar(
                    select(TeamMember.id)
                    .join(Team, Team.id == TeamMember.team_id)
                    .where(
                        Team.supervisor_id == lecturer.id,
                        TeamMember.student_id == diary.student_id,
                    )
                )
                if manages_student is not None:
                    return
        raise _http_error(status.HTTP_403_FORBIDDEN, "You cannot access this diary.")

    report = db.get(Report, report_id)
    if report is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, "The linked report was not found.")
    if current_user.role == UserRole.ADMIN:
        return
    if current_user.role == UserRole.STUDENT:
        student = current_user.student
        if student is not None:
            if report.student_id == student.id:
                return
            if report.team_id is not None:
                is_member = db.scalar(
                    select(TeamMember.id).where(
                        TeamMember.team_id == report.team_id,
                        TeamMember.student_id == student.id,
                    )
                )
                if is_member is not None:
                    return
    elif current_user.role == UserRole.SUPERVISOR:
        lecturer = current_user.lecturer
        if lecturer is not None:
            if report.team_id is not None:
                team = db.get(Team, report.team_id)
                if team is not None and team.supervisor_id == lecturer.id:
                    return
            elif report.student_id is not None:
                manages_student = db.scalar(
                    select(TeamMember.id)
                    .join(Team, Team.id == TeamMember.team_id)
                    .where(
                        Team.supervisor_id == lecturer.id,
                        TeamMember.student_id == report.student_id,
                    )
                )
                if manages_student is not None:
                    return
    raise _http_error(status.HTTP_403_FORBIDDEN, "You cannot access this report.")


def _check_attachment_access(
    db: Session,
    current_user: User,
    attachment: Attachment,
) -> None:
    _assert_target_access(
        db,
        current_user,
        task_id=attachment.task_id,
        diary_id=attachment.diary_id,
        report_id=attachment.report_id,
    )


def _storage_file_path(stored_filename: str | None) -> Path | None:
    if stored_filename is None:
        return None
    if (
        not SAFE_STORED_NAME.fullmatch(stored_filename)
        or Path(stored_filename).name != stored_filename
    ):
        return None

    storage_root = settings.attachment_storage_path
    candidate = storage_root / stored_filename
    if candidate.is_symlink() or candidate.resolve(strict=False).parent != storage_root:
        return None
    return candidate


async def upload_attachment(
    *,
    db: Session,
    current_user: User,
    file: UploadFile,
    task_id: int | None,
    diary_id: int | None,
    report_id: int | None,
) -> AttachmentResponse:
    _assert_target_access(
        db,
        current_user,
        task_id=task_id,
        diary_id=diary_id,
        report_id=report_id,
    )
    if report_id is not None:
        report = db.get(Report, report_id)
        if current_user.role == UserRole.SUPERVISOR:
            raise _http_error(status.HTTP_403_FORBIDDEN, "Giảng viên không thể tải tệp thay cho báo cáo của sinh viên.")
        if report is not None and report.status == ReportStatus.APPROVED:
            raise _http_error(status.HTTP_409_CONFLICT, "Báo cáo đã duyệt và không thể thay đổi tệp.")
    original_name, extension = _clean_original_filename(file.filename)
    mime_type = _validate_declared_mime_type(file.content_type, extension)
    max_file_size = settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    storage_root = settings.attachment_storage_path
    temporary_path: Path | None = None
    stored_path: Path | None = None
    metadata_saved = False
    size = 0

    try:
        storage_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".upload-",
            suffix=".tmp",
            dir=storage_root,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_file_size:
                    raise _http_error(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        f"Files must not exceed {settings.MAX_ATTACHMENT_SIZE_MB} MB.",
                    )
                temporary_file.write(chunk)

        if size == 0:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "The uploaded file is empty.")
        _validate_file_signature(temporary_path, extension)

        stored_filename = f"{uuid.uuid4().hex}{extension}"
        stored_path = storage_root / stored_filename
        os.rename(temporary_path, stored_path)
        temporary_path = None

        attachment = Attachment(
            uploaded_by=current_user.id,
            task_id=task_id,
            diary_id=diary_id,
            report_id=report_id,
            file_name=original_name,
            file_url=stored_filename,
            stored_filename=stored_filename,
            mime_type=mime_type,
            file_size=size,
        )
        try:
            db.add(attachment)
            db.commit()
            metadata_saved = True
            db.refresh(attachment)
        except IntegrityError:
            db.rollback()
            raise _http_error(
                status.HTTP_409_CONFLICT,
                "The linked record changed before the attachment could be saved.",
            ) from None
        except SQLAlchemyError:
            db.rollback()
            raise _http_error(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Unable to save attachment metadata.",
            ) from None
        return AttachmentResponse.model_validate(attachment)
    except HTTPException:
        raise
    except OSError:
        logger.exception("Attachment storage operation failed.")
        raise _http_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Unable to store the uploaded file.",
        ) from None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Failed to remove a temporary attachment file.")
        if stored_path is not None and not metadata_saved:
            try:
                stored_path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Failed to remove an attachment after a database error.")


def get_attachment_file(
    *,
    db: Session,
    attachment_id: int,
    current_user: User,
) -> tuple[Attachment, Path]:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, "Attachment not found.")
    _check_attachment_access(db, current_user, attachment)

    file_path = _storage_file_path(attachment.stored_filename)
    if file_path is None or not file_path.is_file():
        raise _http_error(status.HTTP_404_NOT_FOUND, "Attachment file not found.")
    return attachment, file_path


def list_target_attachments(
    *,
    db: Session,
    task_id: int | None,
    diary_id: int | None,
    report_id: int | None,
    current_user: User,
) -> list[Attachment]:
    _assert_target_access(
        db,
        current_user,
        task_id=task_id,
        diary_id=diary_id,
        report_id=report_id,
    )
    target_column = (
        Attachment.task_id if task_id is not None
        else Attachment.diary_id if diary_id is not None
        else Attachment.report_id
    )
    target_id = task_id if task_id is not None else diary_id if diary_id is not None else report_id
    return list(
        db.scalars(
            select(Attachment)
            .where(target_column == target_id)
            .order_by(Attachment.uploaded_at.asc(), Attachment.id.asc())
        ).all()
    )


def list_task_attachments(
    *,
    db: Session,
    task_id: int,
    current_user: User,
) -> list[Attachment]:
    return list_target_attachments(
        db=db,
        task_id=task_id,
        diary_id=None,
        report_id=None,
        current_user=current_user,
    )


def delete_attachment(
    *,
    db: Session,
    attachment_id: int,
    current_user: User,
) -> None:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, "Attachment not found.")
    _check_attachment_access(db, current_user, attachment)
    if attachment.report_id is not None:
        report = db.get(Report, attachment.report_id)
        if report is not None and report.status == ReportStatus.APPROVED:
            raise _http_error(status.HTTP_409_CONFLICT, "Báo cáo đã duyệt và không thể thay đổi tệp.")

    is_admin = current_user.role == UserRole.ADMIN
    is_uploader = attachment.uploaded_by == current_user.id
    is_supervisor = current_user.role == UserRole.SUPERVISOR
    if not (is_admin or is_uploader or is_supervisor):
        raise _http_error(status.HTTP_403_FORBIDDEN, "You cannot delete this attachment.")

    file_path = _storage_file_path(attachment.stored_filename)
    if attachment.stored_filename is not None and file_path is None:
        raise _http_error(
            status.HTTP_409_CONFLICT,
            "Attachment storage metadata is invalid; the file was not deleted.",
        )

    quarantined_path: Path | None = None
    if file_path is not None and file_path.exists():
        quarantined_path = file_path.with_name(
            f".{file_path.name}.{uuid.uuid4().hex}.deleting"
        )
        try:
            os.replace(file_path, quarantined_path)
        except OSError:
            logger.exception("Unable to stage attachment file deletion.")
            raise _http_error(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Unable to delete the attachment file.",
            ) from None

    try:
        db.delete(attachment)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        if quarantined_path is not None and quarantined_path.exists():
            try:
                os.replace(quarantined_path, file_path)
            except OSError:
                logger.exception("Failed to restore an attachment after database rollback.")
        raise _http_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Unable to delete attachment metadata.",
        ) from None

    if quarantined_path is not None:
        try:
            quarantined_path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Attachment metadata was deleted, but its file cleanup failed.")
            raise _http_error(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Attachment metadata was deleted, but the file could not be removed.",
            ) from None