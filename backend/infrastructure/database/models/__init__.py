"""SQLAlchemy ORM models.

All models inherit from Base (DeclarativeBase) defined in engine.py.
"""

from backend.infrastructure.database.models.base import TimestampMixin, UUIDMixin
from backend.infrastructure.database.models.project import Project
from backend.infrastructure.database.models.video_master import VideoMaster
from backend.infrastructure.database.models.project_video import ProjectVideo
from backend.infrastructure.database.models.analysis import Analysis
from backend.infrastructure.database.models.clip_candidate import ClipCandidate
from backend.infrastructure.database.models.timeline_state import TimelineState
from backend.infrastructure.database.models.export_job import ExportJob
from backend.infrastructure.database.models.caption_track import CaptionTrack
from backend.infrastructure.database.models.processing_queue import ProcessingQueue
from backend.infrastructure.database.models.version_snapshot import VersionSnapshot
from backend.infrastructure.database.models.settings import SettingsEntry
from backend.infrastructure.database.models.provider_config import ProviderConfig
from backend.infrastructure.database.models.model_registry import ModelRegistry

__all__ = [
    "TimestampMixin",
    "UUIDMixin",
    "Project",
    "VideoMaster",
    "ProjectVideo",
    "Analysis",
    "ClipCandidate",
    "TimelineState",
    "ExportJob",
    "CaptionTrack",
    "ProcessingQueue",
    "VersionSnapshot",
    "SettingsEntry",
    "ProviderConfig",
    "ModelRegistry",
]
