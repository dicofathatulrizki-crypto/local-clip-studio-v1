"""Video import API routes — SRS §6.2.2, API Spec §3.2."""

from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.api.deps import get_db_session
from backend.infrastructure.database.repositories.project_repo import ProjectRepository
from backend.infrastructure.database.repositories.video_repo import (
    ProjectVideoRepository,
    VideoMasterRepository,
)
from backend.infrastructure.ffmpeg import FFprobeService
from backend.infrastructure.ffmpeg.locate import FFmpegLocator
from backend.infrastructure.filesystem.directory_manager import DirectoryManager
from backend.infrastructure.filesystem.file_manager import FileManager
from backend.services.import_service import ImportService

router = APIRouter(prefix="/api/v1/projects/{project_id}/videos", tags=["videos"])


# ── Schemas ────────────────────────────────────────────────

class ImportResponse(BaseModel):
    id: str
    video_id: str
    filename: str
    hash: str
    status: str
    progress: float = 0.0
    metadata: dict | None = None

class ImportStatusResponse(BaseModel):
    id: str
    video_id: str
    status: str
    source_path: str
    imported_at: str | None = None

class ValidationResponse(BaseModel):
    valid: bool
    filename: str
    file_size_bytes: int
    has_video: bool
    has_audio: bool


# ── Dependencies ────────────────────────────────────────────

def _get_service(session=Depends(get_db_session)) -> ImportService:
    locator = FFmpegLocator()
    return ImportService(
        video_master_repository=VideoMasterRepository(session),
        project_video_repository=ProjectVideoRepository(session),
        project_repository=ProjectRepository(session),
        file_manager=FileManager(),
        ffprobe_service=FFprobeService(locator.ffprobe_path),
        directory_manager=DirectoryManager(),
    )


# ── Routes ─────────────────────────────────────────────────

@router.post("/import", response_model=ImportResponse, status_code=202)
async def import_video_file(
    project_id: str,
    file: UploadFile = File(...),
    generate_proxy: bool = Form(True),
    svc: ImportService = Depends(_get_service),
):
    import tempfile
    from pathlib import Path

    import uuid

    _CHUNK_SIZE = 1024 * 1024  # 1 MB
    _SAFE_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}

    # Generate a safe UUID filename. Never trust UploadFile.filename (CWE-22).
    raw_name = file.filename or "video.mp4"
    ext = Path(raw_name).suffix.lower()
    if ext not in _SAFE_EXTENSIONS:
        ext = ".mp4"
    safe_name = uuid.uuid4().hex + ext

    tmp = Path(tempfile.mkdtemp(prefix="import_"))
    dest = tmp / safe_name
    with open(dest, "wb") as f:
        while chunk := await file.read(_CHUNK_SIZE):
            f.write(chunk)

    try:
        result = await svc.import_file(project_id=project_id, file_path=dest, generate_proxy=generate_proxy)
        return ImportResponse(
            id=result.id,
            video_id=result.video_id,
            filename=safe_name,
            hash=result.source_path.split("/")[-1].split(".")[0],
            status=result.status,
        )
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

@router.post("/validate", response_model=ValidationResponse)
async def validate_import(
    project_id: str,
    file: UploadFile = File(...),
    svc: ImportService = Depends(_get_service),
):
    import tempfile
    from pathlib import Path

    import uuid

    _CHUNK_SIZE = 1024 * 1024  # 1 MB
    _SAFE_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}

    # Generate a safe UUID filename. Never trust UploadFile.filename (CWE-22).
    raw_name = file.filename or "video.mp4"
    ext = Path(raw_name).suffix.lower()
    if ext not in _SAFE_EXTENSIONS:
        ext = ".mp4"
    safe_name = uuid.uuid4().hex + ext

    tmp = Path(tempfile.mkdtemp(prefix="val_"))
    dest = tmp / safe_name
    with open(dest, "wb") as f:
        while chunk := await file.read(_CHUNK_SIZE):
            f.write(chunk)

    try:
        result = await svc.validate_file(str(dest))
        return ValidationResponse(
            valid=result["valid"],
            filename=result["filename"],
            file_size_bytes=result["file_size_bytes"],
            has_video=result["has_video"],
            has_audio=result["has_audio"],
        )
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

@router.get("/{video_id}/status", response_model=ImportStatusResponse)
async def import_status(project_id: str, video_id: str, svc: ImportService = Depends(_get_service)):
    result = await svc.get_import_status(video_id)
    return ImportStatusResponse(
        id=result.id,
        video_id=result.video_id,
        status=result.status,
        source_path=result.source_path,
    )

@router.post("/{video_id}/cancel", status_code=204)
async def cancel_import(project_id: str, video_id: str, svc: ImportService = Depends(_get_service)):
    await svc.cancel_import(video_id)


# ── URL import (separate endpoint) ─────────────────────────

class URLImportRequest(BaseModel):
    url: str = Field(..., description="YouTube or other video URL")
    generate_proxy: bool = True

@router.post("/import-url", response_model=ImportResponse, status_code=202)
async def import_video_url(
    project_id: str,
    body: URLImportRequest,
    svc: ImportService = Depends(_get_service),
):
    result = await svc.import_url(project_id, body.url)
    return ImportResponse(
        id=result.id,
        video_id=result.video_id,
        filename=result.source_path.split("/")[-1],
        hash="",
        status=result.status,
    )
