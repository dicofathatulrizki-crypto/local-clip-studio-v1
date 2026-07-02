"""API route modules — FastAPI APIRouter instances for each resource group."""

from backend.api.routes.projects import router as projects_router

__all__ = [
    "projects_router",
]
