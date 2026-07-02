"""Project API routes — SRS §6.2.1, API Spec §3.1."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.api.deps import get_db_session
from backend.infrastructure.database.repositories.project_repo import ProjectRepository
from backend.infrastructure.filesystem.directory_manager import DirectoryManager
from backend.infrastructure.filesystem.storage_manager import StorageManager
from backend.services.project_service import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


# ── Request / Response schemas ──────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)

class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None

class DuplicateProjectRequest(BaseModel):
    new_name: str = Field(..., min_length=1, max_length=255)

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_opened_at: datetime | None = None
    is_archived: bool = False

class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    limit: int
    offset: int

class ArchiveResponse(BaseModel):
    path: str
    project_id: str
    archived: bool = True


# ── Dependencies ────────────────────────────────────────────

def _get_service(session=Depends(get_db_session)) -> ProjectService:
    return ProjectService(
        project_repository=ProjectRepository(session),
        directory_manager=DirectoryManager(),
        storage_manager=StorageManager(),
    )


# ── Routes (static paths BEFORE parameterized paths) ────────

@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate, svc: ProjectService = Depends(_get_service)):
    project = await svc.create(name=body.name, description=body.description)
    return ProjectResponse(id=str(project.id), name=project.name, description=project.description,
                           created_at=getattr(project, "created_at", None),
                           updated_at=getattr(project, "updated_at", None))

@router.get("", response_model=ProjectListResponse)
async def list_projects(limit: int = 20, offset: int = 0,
                        svc: ProjectService = Depends(_get_service)):
    projects, total = await svc.list(limit=limit, offset=offset)
    items = [ProjectResponse(id=str(p.id), name=p.name, description=p.description) for p in projects]
    return ProjectListResponse(items=items, total=total, limit=limit, offset=offset)

# ── Static paths ────────────────────────────────────────────

@router.get("/recent", response_model=list[ProjectResponse])
async def recent_projects(count: int = 10, svc: ProjectService = Depends(_get_service)):
    projects = await svc.get_recent(count=count)
    return [ProjectResponse(id=str(p.id), name=p.name, description=p.description) for p in projects]

# ── Parameterized paths ─────────────────────────────────────

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, svc: ProjectService = Depends(_get_service)):
    project = await svc.get(project_id)
    if project is None:
        return JSONResponse(status_code=404, content={"error": {"code": "ERR-NOTFOUND-001", "message": "Project not found"}})
    return ProjectResponse(id=str(project.id), name=project.name, description=project.description,
                           created_at=getattr(project, "created_at", None),
                           updated_at=getattr(project, "updated_at", None))

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, body: ProjectUpdate,
                          svc: ProjectService = Depends(_get_service)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    project = await svc.update(project_id, updates)
    return ProjectResponse(id=str(project.id), name=project.name, description=project.description)

@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, svc: ProjectService = Depends(_get_service)):
    await svc.delete(project_id)

@router.post("/{project_id}/archive", response_model=ArchiveResponse)
async def archive_project(project_id: str, svc: ProjectService = Depends(_get_service)):
    path = await svc.archive(project_id)
    return ArchiveResponse(path=path, project_id=project_id)

@router.post("/{project_id}/restore", response_model=ProjectResponse)
async def restore_project(project_id: str, svc: ProjectService = Depends(_get_service)):
    project = await svc.restore(project_id)
    return ProjectResponse(id=str(project.id), name=project.name, description=project.description)

@router.post("/{project_id}/duplicate", response_model=ProjectResponse, status_code=201)
async def duplicate_project(project_id: str, body: DuplicateProjectRequest,
                             svc: ProjectService = Depends(_get_service)):
    project = await svc.duplicate(project_id, body.new_name)
    return ProjectResponse(id=str(project.id), name=project.name, description=project.description)
