
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.internship_period import PeriodStatus
from app.schemas.internship import (
    InternshipCreate,
    InternshipUpdate,
    InternshipStatusUpdate,
    InternshipResponse,
)
from app.services import internship_service as service


router = APIRouter(
    prefix="/internship-periods",
    tags=["Internships"]
)


@router.get(
    "",
    response_model=list[InternshipResponse]
)
def get_all_internships(db: Session = Depends(get_db)):
    return service.get_all_internships(db)


@router.get(
    "/{internship_id}",
    response_model=InternshipResponse
)
def get_internship(
    internship_id: int,
    db: Session = Depends(get_db)
):
    return service.get_internship_by_id(db, internship_id)


@router.post(
    "",
    response_model=InternshipResponse,
    status_code=status.HTTP_201_CREATED
)
def create_internship(
    data: InternshipCreate,
    db: Session = Depends(get_db)
):
    return service.create_internship(db, data)


@router.put(
    "/{internship_id}",
    response_model=InternshipResponse
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
    response_model=InternshipResponse
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
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_internship(
    internship_id: int,
    db: Session = Depends(get_db)
):
    service.delete_internship(db, internship_id)
    return None
