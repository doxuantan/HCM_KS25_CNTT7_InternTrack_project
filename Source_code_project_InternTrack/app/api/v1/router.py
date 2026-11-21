from fastapi import APIRouter

from app.api.v1.endpoints.attachments import router as attachments_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.internships import router as internships_router
from app.api.v1.endpoints.progress import router as progress_router
from app.api.v1.endpoints.tasks import router as tasks_router
from app.api.v1.endpoints.teams import router as teams_router
from app.api.v1.endpoints.schedules import router as schedules_router
from app.api.v1.endpoints.tasks import router as tasks_router
from app.api.v1.endpoints.users import router as users_router


router = APIRouter(prefix="/api/v1")
router.include_router(attachments_router)
router.include_router(auth_router)
router.include_router(internships_router)
router.include_router(progress_router)
router.include_router(tasks_router)
router.include_router(teams_router)
router.include_router(users_router)
router.include_router(schedules_router)