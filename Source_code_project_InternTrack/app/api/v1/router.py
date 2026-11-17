from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.internships import router as internships_router
from app.api.v1.endpoints.tasks import router as tasks_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(internships_router)
router.include_router(tasks_router)