"""Repository implementations for data access.

Each repository provides:
- CRUD operations via inherited BaseRepository
- Domain entity mapping via mapper classes (create_from_domain, get_domain, update_from_domain)
- Domain-to-ORM translation is handled inside the repository layer — never exposes ORM models to services
- Error translation: SQLAlchemy exceptions → RepositoryError subclasses
"""

from __future__ import annotations

from backend.infrastructure.database.repositories.analysis_repo import AnalysisRepository
from backend.infrastructure.database.repositories.base import BaseRepository
from backend.infrastructure.database.repositories.caption_repo import CaptionRepository
from backend.infrastructure.database.repositories.clip_repo import ClipRepository
from backend.infrastructure.database.repositories.exceptions import (
    ConcurrentUpdateError,
    DuplicateEntityError,
    EntityNotFoundError,
    MappingError,
    RepositoryError,
    RepositoryIntegrityError,
)
from backend.infrastructure.database.repositories.export_repo import ExportRepository
from backend.infrastructure.database.repositories.mappers import (
    AnalysisMapper,
    CaptionMapper,
    ClipMapper,
    ExportMapper,
    ProjectMapper,
    ProviderMapper,
    VideoMapper,
)
from backend.infrastructure.database.repositories.model_registry_repo import (
    ModelRegistryRepository,
)
from backend.infrastructure.database.repositories.plugin_repo import PluginConfigRepository
from backend.infrastructure.database.repositories.project_repo import ProjectRepository
from backend.infrastructure.database.repositories.provider_repo import ProviderRepository
from backend.infrastructure.database.repositories.settings_repo import SettingsRepository
from backend.infrastructure.database.repositories.video_repo import (
    ProjectVideoRepository,
    VideoMasterRepository,
)

__all__ = [
    "AnalysisMapper",
    # Repositories
    "AnalysisRepository",
    # Base
    "BaseRepository",
    "CaptionMapper",
    "CaptionRepository",
    "ClipMapper",
    "ClipRepository",
    # Exceptions
    "ConcurrentUpdateError",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "ExportMapper",
    "ExportRepository",
    # Mappers
    "MappingError",
    "ModelRegistryRepository",
    "PluginConfigRepository",
    "ProjectMapper",
    "ProjectRepository",
    "ProjectVideoRepository",
    "ProviderMapper",
    "ProviderRepository",
    "RepositoryError",
    "RepositoryIntegrityError",
    "SettingsRepository",
    "VideoMapper",
    "VideoMasterRepository",
]
