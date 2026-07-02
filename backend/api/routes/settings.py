"""Settings API routes — SRS §6.2.8, API Spec §3.8."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.deps import get_db_session
from backend.config.encryption import APIKeyEncryption
from backend.infrastructure.database.repositories.settings_repo import SettingsRepository
from backend.services.settings_service import SettingsService

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


# ── Schemas ────────────────────────────────────────────────

class SettingUpdate(BaseModel):
    value: str | int | float | bool | None = None

class BulkUpdate(BaseModel):
    settings: dict[str, str | int | float | bool | None]

class SettingsExportResponse(BaseModel):
    settings: str  # JSON string


# ── Dependencies ────────────────────────────────────────────

def _get_service(session=Depends(get_db_session)) -> SettingsService:
    return SettingsService(
        settings_repository=SettingsRepository(session),
        api_key_encryption=APIKeyEncryption(),
    )


# ── Routes ─────────────────────────────────────────────────

@router.get("")
async def get_all_settings(svc: SettingsService = Depends(_get_service)):
    return await svc.get_all()

@router.get("/{category}")
async def get_settings_category(category: str, svc: SettingsService = Depends(_get_service)):
    return await svc.get_category(category)

@router.get("/{category}/{key}")
async def get_setting(category: str, key: str, svc: SettingsService = Depends(_get_service)):
    full_key = f"{category}.{key}" if category != "general" else key
    value = await svc.get_setting(full_key)
    if value is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": {"code": "ERR-NOTFOUND-001", "message": "Setting not found"}})
    return {"key": full_key, "value": value}

@router.patch("")
async def update_settings(body: BulkUpdate, svc: SettingsService = Depends(_get_service)):
    result = await svc.update_settings(body.settings)
    return result

@router.delete("/{category}/{key}", status_code=204)
async def reset_setting(category: str, key: str, svc: SettingsService = Depends(_get_service)):
    full_key = f"{category}.{key}"
    await svc.reset_setting(full_key)

@router.delete("/{category}", status_code=204)
async def reset_category(category: str, svc: SettingsService = Depends(_get_service)):
    await svc.reset_category(category)

@router.post("/export", response_model=SettingsExportResponse)
async def export_settings(svc: SettingsService = Depends(_get_service)):
    exported = await svc.export_settings()
    return SettingsExportResponse(settings=exported)

@router.post("/import")
async def import_settings(body: BulkUpdate, svc: SettingsService = Depends(_get_service)):
    import json
    result = await svc.import_settings(json.dumps(body.settings))
    return result
