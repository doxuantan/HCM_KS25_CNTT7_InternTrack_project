from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.attachment import AttachmentResponse
from app.services import attachment_service


router = APIRouter(prefix="/attachments", tags=["attachments"])

DOWNLOAD_MEDIA_TYPES = (
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "image/png",
    "image/jpeg",
)


@router.post(
    "/upload",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {"description": "Access to the linked record is denied."},
        status.HTTP_413_CONTENT_TOO_LARGE: {"description": "The file exceeds the configured limit."},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"description": "The file type is unsupported."},
    },
    summary="Upload an attachment",
    description=(
        "Upload a supported document or image. Exactly one of task_id, diary_id, "
        "or report_id must identify the business record this attachment belongs to."
    ),
)
async def upload_attachment(
    file: UploadFile = File(...),
    task_id: int | None = Form(default=None, gt=0),
    diary_id: int | None = Form(default=None, gt=0),
    report_id: int | None = Form(default=None, gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AttachmentResponse:
    return await attachment_service.upload_attachment(
        db=db,
        current_user=current_user,
        file=file,
        task_id=task_id,
        diary_id=diary_id,
        report_id=report_id,
    )


@router.get(
    "/{attachment_id}",
    response_class=FileResponse,
    responses={
        status.HTTP_200_OK: {
            "description": "Attachment file download.",
            "content": {
                media_type: {
                    "schema": {"type": "string", "format": "binary"}
                }
                for media_type in DOWNLOAD_MEDIA_TYPES
            },
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {"description": "Access to the attachment is denied."},
        status.HTTP_404_NOT_FOUND: {"description": "Attachment or file not found."},
    },
    summary="Download an attachment",
    description="Download an attachment as a file after checking access to its linked record.",
)
def get_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    attachment, file_path = attachment_service.get_attachment_file(
        db=db,
        attachment_id=attachment_id,
        current_user=current_user,
    )
    return FileResponse(
        path=file_path,
        filename=attachment.file_name,
        media_type=attachment.mime_type or "application/octet-stream",
        content_disposition_type="attachment",
    )


@router.delete(
    "/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Authentication required."},
        status.HTTP_403_FORBIDDEN: {"description": "Permission to delete the attachment is denied."},
        status.HTTP_404_NOT_FOUND: {"description": "Attachment not found."},
        status.HTTP_409_CONFLICT: {"description": "Attachment storage metadata is invalid."},
    },
    summary="Delete an attachment",
    description="Delete an attachment only when permitted for its linked record.",
)
def delete_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    attachment_service.delete_attachment(
        db=db,
        attachment_id=attachment_id,
        current_user=current_user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)