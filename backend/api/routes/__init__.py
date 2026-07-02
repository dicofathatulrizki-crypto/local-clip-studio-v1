"""API route modules — FastAPI APIRouter instances for each resource group."""

from backend.api.routes.projects import router as projects_router
from backend.api.routes.settings import router as settings_router
from backend.api.routes.system import router as system_router
from backend.api.routes.videos import router as videos_router

__all__ = [
    "projects_router",
    "settings_router",
    "system_router",
    "videos_router",
]
