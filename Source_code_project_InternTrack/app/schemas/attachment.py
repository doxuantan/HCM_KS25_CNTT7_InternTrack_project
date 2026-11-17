from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    mime_type: str | None
    file_size: int | None
    uploaded_by: int
    uploaded_at: datetime
    task_id: int | None
    diary_id: int | None
    report_id: int | None