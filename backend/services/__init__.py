"""Application service layer — business logic orchestration.

Modules:
    B5: ProjectService — project lifecycle management (CRUD, archive, restore, duplicate)
    B6: ImportService — video file import, hash dedup, metadata extraction
    B7: SettingsService — application settings management (SRS §10.6)
    B8: ProviderService — AI provider lifecycle management (SRS §10.5)
    B9: PluginService — plugin lifecycle management (Architecture Blueprint §8)
"""

from backend.services.import_service import ImportService
from backend.services.plugin_service import PluginService
from backend.services.project_service import ProjectService
from backend.services.provider_service import ProviderService
from backend.services.settings_service import SettingsService

__all__ = [
    "ImportService",
    "PluginService",
    "ProjectService",
    "ProviderService",
    "SettingsService",
]
