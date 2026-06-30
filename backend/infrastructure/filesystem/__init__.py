"""
Filesystem and storage subsystem for Local Clip Studio.

Provides a complete storage management layer with specialized managers:
- DirectoryManager: application directory structure creation and path utilities
- FileManager: atomic file operations, SHA-256 hashing, streaming, progress
- StorageManager: disk space monitoring, storage quotas, usage tracking
- TemporaryStorageManager: temp file lifecycle, age-based expiration
- CacheManager: LRU cache eviction, size limits, periodic cleanup
- ProxyStorageManager: proxy video storage and lifecycle
- ExportStorageManager: export output management and naming
- ModelStorageManager: AI model file storage and integrity
- BackupManager: project backup, restore, version history
- CleanupScheduler: scheduled cleanup and policy enforcement
"""
from __future__ import annotations

from backend.infrastructure.filesystem.backup_manager import BackupManager
from backend.infrastructure.filesystem.cache_manager import CacheManager
from backend.infrastructure.filesystem.cleanup_scheduler import CleanupScheduler
from backend.infrastructure.filesystem.directory_manager import DirectoryManager
from backend.infrastructure.filesystem.export_manager import ExportStorageManager
from backend.infrastructure.filesystem.file_manager import FileManager
from backend.infrastructure.filesystem.model_manager import ModelStorageManager
from backend.infrastructure.filesystem.proxy_manager import ProxyStorageManager
from backend.infrastructure.filesystem.storage_manager import StorageManager
from backend.infrastructure.filesystem.temp_manager import TemporaryStorageManager

__all__ = [
    "BackupManager",
    "CacheManager",
    "CleanupScheduler",
    "DirectoryManager",
    "ExportStorageManager",
    "FileManager",
    "ModelStorageManager",
    "ProxyStorageManager",
    "StorageManager",
    "TemporaryStorageManager",
]
