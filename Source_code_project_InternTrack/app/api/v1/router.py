from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.internships import router as internships_router
from app.api.v1.endpoints.teams import router as teams_router
from app.api.v1.endpoints.users import router as users_router


router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(internships_router)
router.include_router(teams_router)
router.include_router(users_router)