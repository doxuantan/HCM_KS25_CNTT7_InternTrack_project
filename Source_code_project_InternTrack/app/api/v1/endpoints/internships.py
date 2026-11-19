
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_role
from app.models.internship_period import PeriodStatus
from app.models.user import User, UserRole
from app.schemas.internship import (
    InternshipCreate,
    InternshipUpdate,
    InternshipStatusUpdate,
    InternshipResponse,
)
from app.services import internship_service as service


router = APIRouter(
    prefix="/internship-periods",
    tags=["Internships"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=list[InternshipResponse]
)
def get_all_internships(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_all_internships(db, current_user)


@router.get(
    "/{internship_id}",
    response_model=InternshipResponse
)
def get_internship(
    internship_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_internship_by_id(db, internship_id, current_user)


@router.post(
    "",
    response_model=InternshipResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def create_internship(
    data: InternshipCreate,
    db: Session = Depends(get_db)
):
    return service.create_internship(db, data)


@router.put(
    "/{internship_id}",
    response_model=InternshipResponse,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def update_internship(
    internship_id: int,
    data: InternshipUpdate,
    db: Session = Depends(get_db)
):
    return service.update_internship(
        db,
        internship_id,
        data
    )


@router.patch(
    "/{internship_id}/status",
    response_model=InternshipResponse,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def update_internship_status(
    internship_id: int,
    data: InternshipStatusUpdate,
    db: Session = Depends(get_db)
):
    return service.update_internship_status(
        db,
        internship_id,
        data.status
    )


@router.delete(
    "/{internship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def delete_internship(
    internship_id: int,
    db: Session = Depends(get_db)
):
    service.delete_internship(db, internship_id)
    return None
