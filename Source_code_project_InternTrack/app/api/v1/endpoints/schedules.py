from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.schedule import ScheduleCreate, ScheduleResponse, ScheduleUpdate
from app.services import schedule_service


router = APIRouter(prefix="/schedules", tags=["Schedules"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    data: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScheduleResponse:
    return schedule_service.create_schedule(db, data, current_user)


@router.get("", response_model=list[ScheduleResponse])
def list_schedules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ScheduleResponse]:
    return schedule_service.get_schedules(db, current_user)


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScheduleResponse:
    return schedule_service.get_schedule(db, schedule_id, current_user)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScheduleResponse:
    return schedule_service.update_schedule(db, schedule_id, data, current_user)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    schedule_service.delete_schedule(db, schedule_id, current_user)