"""System API routes — SRS §6.2.9, API Spec §3.9."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend import __version__, __app_name__
from backend.api.deps import get_db_session
from backend.config.encryption import EncryptionKeyManager
from backend.config.settings import Settings
from backend.infrastructure.database.repositories.plugin_repo import PluginConfigRepository
from backend.infrastructure.database.repositories.provider_repo import ProviderRepository
from backend.infrastructure.database.repositories.settings_repo import SettingsRepository
from backend.infrastructure.plugins.registry import PluginRegistry
from backend.services.plugin_service import PluginService
from backend.services.provider_service import ProviderService
from backend.services.settings_service import SettingsService

router = APIRouter(prefix="/api/v1/system", tags=["system"])


# ── Schemas ────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    app_name: str

class VersionResponse(BaseModel):
    version: str
    app_name: str
    python_version: str
    environment: str

class CapabilitiesResponse(BaseModel):
    supported_formats: list[str]
    max_import_size_gb: int
    max_concurrent_jobs: int

class StorageResponse(BaseModel):
    app_directory: str
    total_gb: float
    used_gb: float
    free_gb: float

class PluginSummary(BaseModel):
    total: int
    active: int
    failed: int

class ProviderSummary(BaseModel):
    total: int
    enabled: int


# ── Dependencies ────────────────────────────────────────────

def _get_settings_service(session=Depends(get_db_session)) -> SettingsService:
    return SettingsService(settings_repository=SettingsRepository(session))

def _get_provider_service(session=Depends(get_db_session)) -> ProviderService:
    from backend.infrastructure.database.repositories.model_registry_repo import (
        ModelRegistryRepository,
    )
    return ProviderService(
        provider_repository=ProviderRepository(session),
        model_registry_repository=ModelRegistryRepository(session),
        plugin_registry=PluginRegistry(),
    )

def _get_plugin_service(session=Depends(get_db_session)) -> PluginService:
    return PluginService(
        plugin_registry=PluginRegistry(),
        plugin_config_repository=PluginConfigRepository(session),
    )


# ── Routes ─────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        version=__version__,
        app_name=__app_name__,
    )

@router.get("/version", response_model=VersionResponse)
async def version():
    import sys
    settings = Settings.get_instance()
    return VersionResponse(
        version=__version__,
        app_name=__app_name__,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        environment=settings.environment,
    )

@router.get("/capabilities", response_model=CapabilitiesResponse)
async def capabilities():
    return CapabilitiesResponse(
        supported_formats=[".mp4", ".mov", ".mkv", ".avi", ".webm"],
        max_import_size_gb=50,
        max_concurrent_jobs=2,
    )

@router.get("/storage", response_model=StorageResponse)
async def storage():
    import shutil
    settings = Settings.get_instance()
    path = settings.storage.effective_path
    total, used, free = shutil.disk_usage(path)
    return StorageResponse(
        app_directory=str(path),
        total_gb=round(total / (1024**3), 2),
        used_gb=round(used / (1024**3), 2),
        free_gb=round(free / (1024**3), 2),
    )

@router.get("/providers", response_model=ProviderSummary)
async def provider_summary(svc: ProviderService = Depends(_get_provider_service)):
    providers = await svc.list_providers()
    return ProviderSummary(
        total=len(providers),
        enabled=sum(1 for p in providers if p.enabled),
    )

@router.get("/plugins", response_model=PluginSummary)
async def plugin_summary(svc: PluginService = Depends(_get_plugin_service)):
    stats = await svc.get_statistics()
    return PluginSummary(
        total=stats.get("total", 0),
        active=stats.get("by_state", {}).get("active", 0),
        failed=stats.get("by_state", {}).get("error", 0),
    )
