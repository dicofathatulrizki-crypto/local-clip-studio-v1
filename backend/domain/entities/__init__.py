"""Domain entities for Local Clip Studio.

Entities have identity (unique ID) and encapsulate business behavior.
They are not anemic data models — they enforce invariants, validate
state transitions, and implement business rules.

Architecture:
    - Zero imports from infrastructure (no SQLAlchemy, FastAPI, etc.)
    - Pure Python standard library only
    - Business logic centralized in entity methods
"""

from backend.domain.entities.analysis import Analysis
from backend.domain.entities.caption import Caption
from backend.domain.entities.clip import Clip
from backend.domain.entities.export import Export
from backend.domain.entities.plugin import Plugin, PluginInfo
from backend.domain.entities.project import Project
from backend.domain.entities.provider import Provider
from backend.domain.entities.video import Video

__all__ = [
    "Analysis",
    "Caption",
    "Clip",
    "Export",
    "Plugin",
    "PluginInfo",
    "Project",
    "Provider",
    "Video",
]
