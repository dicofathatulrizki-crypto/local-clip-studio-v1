"""Bidirectional mappers between domain entities and ORM models.

Each mapper handles:
- ``to_domain(orm_model) -> DomainEntity`` — ORM → Domain
- ``to_orm(domain_entity) -> ORMModel`` — Domain → ORM (for creation)
- ``update_orm(domain_entity, orm_model) -> None`` — Domain → ORM (for updates)

Architecture:
    - Mappers are pure functions with no side effects
    - Only the repository layer calls mappers
    - No business logic in mappers — only field mapping
"""

from __future__ import annotations

from typing import Any

from backend.domain.entities.analysis import Analysis as DomainAnalysis
from backend.domain.entities.caption import Caption as DomainCaption
from backend.domain.entities.clip import Clip as DomainClip
from backend.domain.entities.export import Export as DomainExport
from backend.domain.entities.plugin import Plugin as DomainPlugin
from backend.domain.entities.plugin import PluginInfo as DomainPluginInfo
from backend.domain.entities.project import Project as DomainProject
from backend.domain.entities.provider import Provider as DomainProvider
from backend.domain.entities.video import Video as DomainVideo
from backend.domain.state_machines import (
    AnalysisState,
    ClipState,
    ExportState,
    PluginState,
    ProjectState,
    UploadState,
)
from backend.domain.value_objects import (
    AnalysisId,
    CaptionId,
    ClipId,
    FileHash,
    PluginId,
    ProjectId,
    ProviderId,
    VideoId,
)
from backend.infrastructure.database.models.analysis import Analysis as ORMAnalysis
from backend.infrastructure.database.models.caption_track import CaptionTrack as ORMCaption
from backend.infrastructure.database.models.clip_candidate import ClipCandidate as ORMClip
from backend.infrastructure.database.models.export_job import ExportJob as ORMExport
from backend.infrastructure.database.models.model_registry import ModelRegistry as ORMModelRegistry
from backend.infrastructure.database.models.project import Project as ORMProject
from backend.infrastructure.database.models.project_video import ProjectVideo as ORMProjectVideo
from backend.infrastructure.database.models.provider_config import ProviderConfig as ORMProvider
from backend.infrastructure.database.models.video_master import VideoMaster as ORMVideoMaster
from backend.infrastructure.database.repositories.exceptions import MappingError


# ---------------------------------------------------------------------------
# Project mapper
# ---------------------------------------------------------------------------


class ProjectMapper:
    """Maps between Domain Project and ORM Project models."""

    @staticmethod
    def to_domain(orm: ORMProject) -> DomainProject:
        """Convert ORM Project to Domain Project."""
        state = ProjectState.ARCHIVED if orm.is_archived else ProjectState.ACTIVE
        return DomainProject(
            id=ProjectId(value=orm.id),
            name=orm.name,
            description=orm.description,
            state=state,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            last_opened_at=orm.last_opened_at,
            settings=orm.settings or {},
            thumbnail_path=orm.thumbnail_path,
            version=orm.version,
        )

    @staticmethod
    def to_orm(domain: DomainProject) -> ORMProject:
        """Convert Domain Project to ORM Project for creation."""
        return ORMProject(
            id=str(domain.id),
            name=domain.name,
            description=domain.description,
            is_archived=1 if domain.state == ProjectState.ARCHIVED else 0,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
            last_opened_at=domain.last_opened_at,
            settings=domain.settings or None,
            thumbnail_path=domain.thumbnail_path,
            version=domain.version,
            storage_path="",
        )

    @staticmethod
    def update_orm(domain: DomainProject, orm: ORMProject) -> None:
        """Update ORM Project fields from Domain Project."""
        orm.name = domain.name
        orm.description = domain.description
        orm.is_archived = 1 if domain.state in (ProjectState.ARCHIVED, ProjectState.DELETED) else 0
        orm.last_opened_at = domain.last_opened_at
        orm.settings = domain.settings or None
        orm.thumbnail_path = domain.thumbnail_path
        orm.version = domain.version
        orm.updated_at = domain.updated_at


# ---------------------------------------------------------------------------
# Video master mapper
# ---------------------------------------------------------------------------


class VideoMapper:
    """Maps between Domain Video and ORM VideoMaster models."""

    @staticmethod
    def to_domain(orm: ORMVideoMaster) -> DomainVideo:
        """Convert ORM VideoMaster to Domain Video."""
        return DomainVideo(
            id=VideoId(value=orm.id),
            hash=FileHash(value=orm.hash),
            original_filename=orm.original_filename,
            file_size_bytes=orm.file_size_bytes,
            duration_ms=orm.duration_ms,
            width=orm.width,
            height=orm.height,
            fps=orm.fps,
            video_codec=orm.video_codec,
            audio_codec=orm.audio_codec,
            bitrate=orm.bitrate,
            storage_path=orm.storage_path,
            upload_state=UploadState.READY,
            imported_at=orm.imported_at,
        )

    @staticmethod
    def to_orm(domain: DomainVideo) -> ORMVideoMaster:
        """Convert Domain Video to ORM VideoMaster for creation."""
        return ORMVideoMaster(
            id=str(domain.id),
            hash=str(domain.hash),
            original_filename=domain.original_filename,
            file_size_bytes=domain.file_size_bytes,
            duration_ms=domain.duration_ms,
            width=domain.width,
            height=domain.height,
            fps=domain.fps,
            video_codec=domain.video_codec,
            audio_codec=domain.audio_codec,
            bitrate=domain.bitrate,
            storage_path=domain.storage_path,
            imported_at=domain.imported_at or domain.created_at if hasattr(domain, 'created_at') else None,
        )

    @staticmethod
    def update_orm(domain: DomainVideo, orm: ORMVideoMaster) -> None:
        """Update ORM VideoMaster fields from Domain Video."""
        orm.original_filename = domain.original_filename
        orm.file_size_bytes = domain.file_size_bytes
        orm.duration_ms = domain.duration_ms
        orm.width = domain.width
        orm.height = domain.height
        orm.fps = domain.fps
        orm.video_codec = domain.video_codec
        orm.audio_codec = domain.audio_codec
        orm.bitrate = domain.bitrate
        orm.storage_path = domain.storage_path


# ---------------------------------------------------------------------------
# Analysis mapper
# ---------------------------------------------------------------------------


class AnalysisMapper:
    """Maps between Domain Analysis and ORM Analysis models."""

    @staticmethod
    def to_domain(orm: ORMAnalysis) -> DomainAnalysis:
        """Convert ORM Analysis to Domain Analysis."""
        status_str = orm.status or "queued"
        try:
            status = AnalysisState(status_str)
        except ValueError:
            status = AnalysisState.QUEUED

        return DomainAnalysis(
            id=AnalysisId(value=orm.id),
            video_id=VideoId(value=orm.video_id),
            status=status,
            transcript=orm.transcript,
            speakers=orm.speakers,
            scenes=orm.scenes,
            topics=orm.topics,
            keywords=orm.keywords,
            emotions=orm.emotions,
            hooks=orm.hooks,
            chapters=orm.chapters,
            quality_score=orm.quality_score,
            quality_dimensions=orm.quality_details,
            duration_ms=orm.duration_ms,
            started_at=orm.started_at,
            completed_at=orm.completed_at,
            created_at=orm.created_at,
        )

    @staticmethod
    def to_orm(domain: DomainAnalysis) -> ORMAnalysis:
        """Convert Domain Analysis to ORM Analysis for creation."""
        return ORMAnalysis(
            id=str(domain.id),
            video_id=str(domain.video_id),
            status=domain.status.value,
            transcript=domain.transcript,
            speakers=domain.speakers,
            scenes=domain.scenes,
            topics=domain.topics,
            keywords=domain.keywords,
            emotions=domain.emotions,
            hooks=domain.hooks,
            chapters=domain.chapters,
            quality_score=domain.quality_score,
            quality_details=domain.quality_dimensions,
            duration_ms=domain.duration_ms,
            started_at=domain.started_at,
            completed_at=domain.completed_at,
            created_at=domain.created_at,
        )

    @staticmethod
    def update_orm(domain: DomainAnalysis, orm: ORMAnalysis) -> None:
        """Update ORM Analysis fields from Domain Analysis."""
        orm.status = domain.status.value
        orm.transcript = domain.transcript
        orm.speakers = domain.speakers
        orm.scenes = domain.scenes
        orm.topics = domain.topics
        orm.keywords = domain.keywords
        orm.emotions = domain.emotions
        orm.hooks = domain.hooks
        orm.chapters = domain.chapters
        orm.quality_score = domain.quality_score
        orm.quality_details = domain.quality_dimensions
        orm.duration_ms = domain.duration_ms
        orm.started_at = domain.started_at
        orm.completed_at = domain.completed_at


# ---------------------------------------------------------------------------
# Clip mapper
# ---------------------------------------------------------------------------


class ClipMapper:
    """Maps between Domain Clip and ORM ClipCandidate models."""

    @staticmethod
    def to_domain(orm: ORMClip) -> DomainClip:
        """Convert ORM ClipCandidate to Domain Clip."""
        status_str = orm.status or "candidate"
        try:
            status = ClipState(status_str)
        except ValueError:
            status = ClipState.CANDIDATE

        hashtags: list[str] = []
        if orm.hashtags and isinstance(orm.hashtags, list):
            hashtags = [str(t) for t in orm.hashtags]

        return DomainClip(
            id=ClipId(value=orm.id),
            video_id=VideoId(value=orm.video_id),
            start_ms=orm.start_ms,
            end_ms=orm.end_ms,
            quality_score=orm.quality_score,
            virality_score=orm.virality_score,
            hook_score=orm.hook_score,
            title=orm.title,
            description=orm.description,
            hashtags=hashtags,
            status=status,
            rank=orm.rank,
            created_at=orm.created_at,
        )

    @staticmethod
    def to_orm(domain: DomainClip) -> ORMClip:
        """Convert Domain Clip to ORM ClipCandidate for creation."""
        return ORMClip(
            id=str(domain.id),
            video_id=str(domain.video_id),
            start_ms=domain.start_ms,
            end_ms=domain.end_ms,
            quality_score=domain.quality_score,
            virality_score=domain.virality_score,
            hook_score=domain.hook_score,
            title=domain.title,
            description=domain.description,
            hashtags=domain.hashtags or None,
            status=domain.status.value,
            rank=domain.rank,
            created_at=domain.created_at,
        )

    @staticmethod
    def update_orm(domain: DomainClip, orm: ORMClip) -> None:
        """Update ORM ClipCandidate from Domain Clip."""
        orm.start_ms = domain.start_ms
        orm.end_ms = domain.end_ms
        orm.quality_score = domain.quality_score
        orm.virality_score = domain.virality_score
        orm.hook_score = domain.hook_score
        orm.title = domain.title
        orm.description = domain.description
        orm.hashtags = domain.hashtags or None
        orm.status = domain.status.value
        orm.rank = domain.rank


# ---------------------------------------------------------------------------
# Caption mapper
# ---------------------------------------------------------------------------


class CaptionMapper:
    """Maps between Domain Caption and ORM CaptionTrack models."""

    @staticmethod
    def to_domain(orm: ORMCaption) -> DomainCaption:
        """Convert ORM CaptionTrack to Domain Caption."""
        return DomainCaption(
            id=CaptionId(value=orm.id),
            clip_id=ClipId(value=orm.clip_id),
            language=orm.language,
            style=orm.style or {},
            captions=orm.captions or [],
            is_source_language=bool(orm.is_source_language),
            created_at=orm.created_at,
        )

    @staticmethod
    def to_orm(domain: DomainCaption) -> ORMCaption:
        """Convert Domain Caption to ORM CaptionTrack for creation."""
        return ORMCaption(
            id=str(domain.id),
            clip_id=str(domain.clip_id) if domain.clip_id else "",
            language=domain.language,
            style=domain.style or None,
            captions=domain.captions,
            is_source_language=domain.is_source_language,
            created_at=domain.created_at,
        )

    @staticmethod
    def update_orm(domain: DomainCaption, orm: ORMCaption) -> None:
        """Update ORM CaptionTrack from Domain Caption."""
        orm.language = domain.language
        orm.style = domain.style or None
        orm.captions = domain.captions
        orm.is_source_language = domain.is_source_language


# ---------------------------------------------------------------------------
# Export mapper
# ---------------------------------------------------------------------------


class ExportMapper:
    """Maps between Domain Export and ORM ExportJob models."""

    @staticmethod
    def to_domain(orm: ORMExport) -> DomainExport:
        """Convert ORM ExportJob to Domain Export."""
        status_str = orm.status or "pending"
        try:
            status = ExportState(status_str)
        except ValueError:
            status = ExportState.PENDING

        return DomainExport(
            id=orm.id,
            clip_id=orm.clip_id,
            format=orm.format,
            preset=orm.preset,
            status=status,
            progress=orm.progress,
            output_path=orm.output_path,
            error_message=orm.error_message,
            started_at=orm.started_at,
            completed_at=orm.completed_at,
            created_at=orm.created_at,
        )

    @staticmethod
    def to_orm(domain: DomainExport) -> ORMExport:
        """Convert Domain Export to ORM ExportJob for creation."""
        return ORMExport(
            id=domain.id,
            clip_id=domain.clip_id,
            format=domain.format,
            preset=domain.preset,
            status=domain.status.value,
            progress=domain.progress,
            output_path=domain.output_path,
            error_message=domain.error_message,
            started_at=domain.started_at,
            completed_at=domain.completed_at,
            created_at=domain.created_at,
        )

    @staticmethod
    def update_orm(domain: DomainExport, orm: ORMExport) -> None:
        """Update ORM ExportJob from Domain Export."""
        orm.format = domain.format
        orm.preset = domain.preset
        orm.status = domain.status.value
        orm.progress = domain.progress
        orm.output_path = domain.output_path
        orm.error_message = domain.error_message
        orm.started_at = domain.started_at
        orm.completed_at = domain.completed_at


# ---------------------------------------------------------------------------
# Provider mapper
# ---------------------------------------------------------------------------


class ProviderMapper:
    """Maps between Domain Provider and ORM ProviderConfig models."""

    @staticmethod
    def to_domain(orm: ORMProvider) -> DomainProvider:
        """Convert ORM ProviderConfig to Domain Provider."""
        config = orm.config or {}

        return DomainProvider(
            id=ProviderId(value=orm.provider_id),
            name=config.get("name", orm.provider_id),
            enabled=bool(orm.enabled),
            supported_tasks=config.get("supported_tasks", []),
            configured=bool(config.get("api_key")),
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            models=config.get("models", {}),
            defaults=config.get("defaults", {
                "temperature": 0.7,
                "max_tokens": 4096,
                "timeout": 60,
                "retry_count": 3,
            }),
        )

    @staticmethod
    def to_orm(domain: DomainProvider) -> ORMProvider:
        """Convert Domain Provider to ORM ProviderConfig for creation."""
        config = {
            "name": domain.name,
            "supported_tasks": domain.supported_tasks,
            "api_key": domain.api_key,
            "base_url": domain.base_url,
            "models": domain.models,
            "defaults": domain.defaults,
        }
        return ORMProvider(
            provider_id=str(domain.id),
            enabled=domain.enabled,
            config=config,
            task_routing={},
        )

    @staticmethod
    def update_orm(domain: DomainProvider, orm: ORMProvider) -> None:
        """Update ORM ProviderConfig from Domain Provider."""
        orm.enabled = domain.enabled
        orm.config = {
            "name": domain.name,
            "supported_tasks": domain.supported_tasks,
            "api_key": domain.api_key,
            "base_url": domain.base_url,
            "models": domain.models,
            "defaults": domain.defaults,
        }


# ---------------------------------------------------------------------------
# Model Registry mapper (domain→ORM only — no domain entity for this yet)
# ---------------------------------------------------------------------------


class ModelRegistryMapper:
    """Maps between model registry data and ORM ModelRegistry models."""

    @staticmethod
    def to_dict(orm: ORMModelRegistry) -> dict[str, Any]:
        """Convert ORM ModelRegistry to dict."""
        return {
            "model_id": orm.model_id,
            "model_type": orm.model_type,
            "size_mb": orm.size_mb,
            "vram_mb": orm.vram_mb,
            "path": orm.path,
            "status": orm.status,
            "download_progress": orm.download_progress,
            "version": orm.version,
            "checksum": orm.checksum,
            "downloaded_at": orm.downloaded_at,
            "created_at": orm.created_at,
        }
