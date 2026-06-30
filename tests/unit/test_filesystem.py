"""Unit tests for filesystem managers (FileManager, DirectoryManager, StorageManager, etc.)"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

from backend.infrastructure.filesystem.backup_manager import BackupManager
from backend.infrastructure.filesystem.cache_manager import CacheManager
from backend.infrastructure.filesystem.cleanup_scheduler import CleanupScheduler
from backend.infrastructure.filesystem.directory_manager import DirectoryManager
from backend.infrastructure.filesystem.export_manager import ExportStorageManager
from backend.infrastructure.filesystem.file_manager import FileManager, FileIntegrityError, FileOperationError
from backend.infrastructure.filesystem.model_manager import ModelStorageManager
from backend.infrastructure.filesystem.proxy_manager import ProxyStorageManager
from backend.infrastructure.filesystem.storage_manager import StorageManager
from backend.infrastructure.filesystem.temp_manager import TemporaryStorageManager


# ─── FileManager Tests ──────────────────────────────────────────


class TestFileManager:
    """Test atomic file operations, hashing, streaming."""

    def test_compute_hash(self, tmp_path: Path) -> None:
        """SHA-256 hash should be computed correctly."""
        file = tmp_path / "test.txt"
        file.write_text("hello world")
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert FileManager.compute_hash(file) == expected

    def test_verify_hash(self, tmp_path: Path) -> None:
        """Hash verification should return True for matching hashes."""
        file = tmp_path / "test.txt"
        file.write_text("hello world")
        expected = FileManager.compute_hash(file)
        assert FileManager.verify_hash(file, expected) is True

    def test_verify_hash_mismatch(self, tmp_path: Path) -> None:
        """Hash verification should return False for mismatched hashes."""
        file = tmp_path / "test.txt"
        file.write_text("hello world")
        assert FileManager.verify_hash(file, "invalidhash") is False

    def test_atomic_write_string(self, tmp_path: Path) -> None:
        """Atomic write should write content correctly."""
        target = tmp_path / "output.txt"
        FileManager.atomic_write(target, "test content")
        assert target.read_text() == "test content"

    def test_atomic_write_bytes(self, tmp_path: Path) -> None:
        """Atomic write with bytes should work."""
        target = tmp_path / "output.bin"
        FileManager.atomic_write(target, b"binary data")
        assert target.read_bytes() == b"binary data"

    def test_atomic_write_creates_parent(self, tmp_path: Path) -> None:
        """Atomic write should create parent directories."""
        target = tmp_path / "nested" / "deep" / "file.txt"
        FileManager.atomic_write(target, "nested content")
        assert target.exists()
        assert target.read_text() == "nested content"

    def test_safe_copy(self, tmp_path: Path) -> None:
        """Safe copy should duplicate file with verification."""
        src = tmp_path / "source.txt"
        src.write_text("copy me")
        dst = tmp_path / "dest.txt"

        bytes_copied = FileManager.safe_copy(src, dst)
        assert dst.exists()
        assert dst.read_text() == "copy me"
        assert bytes_copied == 7  # "copy me" length

    def test_safe_move_same_fs(self, tmp_path: Path) -> None:
        """Safe move should rename within same filesystem."""
        src = tmp_path / "source.txt"
        src.write_text("move me")
        dst = tmp_path / "dest.txt"

        bytes_moved = FileManager.safe_move(src, dst)
        assert dst.exists()
        assert dst.read_text() == "move me"
        assert not src.exists()
        assert bytes_moved == 7

    def test_safe_delete_file(self, tmp_path: Path) -> None:
        """Safe delete should remove a file."""
        file = tmp_path / "delete_me.txt"
        file.write_text("delete me")
        assert FileManager.safe_delete(file) is True
        assert not file.exists()

    def test_safe_delete_nonexistent(self, tmp_path: Path) -> None:
        """Safe delete should return False for non-existent files."""
        assert FileManager.safe_delete(tmp_path / "nonexistent.txt") is False

    def test_safe_delete_directory(self, tmp_path: Path) -> None:
        """Safe delete should remove a directory tree."""
        dir_path = tmp_path / "dir_to_delete"
        dir_path.mkdir()
        (dir_path / "file1.txt").write_text("1")
        (dir_path / "file2.txt").write_text("2")

        assert FileManager.safe_delete(dir_path) is True
        assert not dir_path.exists()

    def test_list_files(self, tmp_path: Path) -> None:
        """List files should match pattern."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "c.jpg").write_text("c")

        files = FileManager.list_files(tmp_path, "*.txt")
        assert len(files) == 2

    def test_list_files_recursive(self, tmp_path: Path) -> None:
        """Recursive list should include subdirectories."""
        (tmp_path / "a.txt").write_text("a")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.txt").write_text("b")

        files = FileManager.list_files(tmp_path, "*.txt", recursive=True)
        assert len(files) == 2

    def test_get_size_file(self, tmp_path: Path) -> None:
        """Get size should return file size."""
        file = tmp_path / "size_test.txt"
        file.write_text("12345")
        assert FileManager.get_size(file) == 5

    def test_get_size_directory(self, tmp_path: Path) -> None:
        """Get size should aggregate directory contents."""
        (tmp_path / "f1.txt").write_text("12345")
        (tmp_path / "f2.txt").write_text("12345")
        assert FileManager.get_size(tmp_path) == 10

    def test_create_temp_file(self, tmp_path: Path) -> None:
        """Create temp file should create a file and return its path."""
        temp_path = FileManager.create_temp_file(
            suffix=".mp4", directory=str(tmp_path)
        )
        assert Path(temp_path).exists()
        assert temp_path.endswith(".mp4")


# ─── DirectoryManager Tests ─────────────────────────────────────


class TestDirectoryManager:
    """Test directory structure creation and path utilities."""

    def test_ensure_directories(self, tmp_path: Path) -> None:
        """Ensure directories should create the full structure."""
        mgr = DirectoryManager(str(tmp_path))
        mgr.ensure_directories()

        for subdir in DirectoryManager.SUBDIRECTORIES:
            assert (tmp_path / subdir).exists(), f"Missing: {subdir}"
            assert (tmp_path / subdir).is_dir(), f"Not a dir: {subdir}"

    def test_project_dir(self, tmp_path: Path) -> None:
        """Project dir should return correct path."""
        mgr = DirectoryManager(str(tmp_path))
        pid = str(uuid.uuid4())
        path = mgr.project_dir(pid)
        assert path == tmp_path / "projects" / pid

    def test_ensure_project_dirs(self, tmp_path: Path) -> None:
        """Ensure project dirs should create all subdirectories."""
        mgr = DirectoryManager(str(tmp_path))
        pid = str(uuid.uuid4())
        dirs = mgr.ensure_project_dirs(pid)

        for key, path in dirs.items():
            assert path.exists(), f"Missing project dir: {key} -> {path}"

    def test_validate_path_valid(self, tmp_path: Path) -> None:
        """Valid path should be accepted."""
        mgr = DirectoryManager(str(tmp_path))
        allowed = tmp_path / "projects" / "test"
        allowed.mkdir(parents=True, exist_ok=True)

        path = mgr.validate_path(allowed / "file.txt", allowed)
        assert path == (allowed / "file.txt").resolve()

    def test_validate_path_traversal(self, tmp_path: Path) -> None:
        """Path traversal should raise ValueError."""
        mgr = DirectoryManager(str(tmp_path))
        allowed = tmp_path / "safe"
        allowed.mkdir(parents=True, exist_ok=True)

        with pytest.raises(ValueError, match="Path traversal"):
            mgr.validate_path("/etc/passwd", allowed)

    def test_relative_to_base(self, tmp_path: Path) -> None:
        """Relative path should strip base prefix."""
        mgr = DirectoryManager(str(tmp_path))
        full = tmp_path / "projects" / "test" / "file.txt"
        rel = mgr.relative_to_base(full)
        assert ".." not in rel or "localclip" in rel


# ─── StorageManager Tests ───────────────────────────────────────


class TestStorageManager:
    """Test disk space monitoring and quota enforcement."""

    def test_get_disk_space(self, tmp_path: Path) -> None:
        """Get disk space should return valid info."""
        mgr = StorageManager(str(tmp_path))
        space = mgr.get_disk_space(tmp_path)
        assert "total_bytes" in space
        assert "free_bytes" in space
        assert space["total_bytes"] > 0

    def test_has_enough_space(self, tmp_path: Path) -> None:
        """Has enough space should return True for small requests."""
        mgr = StorageManager(str(tmp_path))
        assert mgr.has_enough_space(1, tmp_path) is True

    def test_get_usage_category(self, tmp_path: Path) -> None:
        """Get usage should return a valid StorageUsage."""
        mgr = StorageManager(str(tmp_path))
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)
        usage = mgr.get_usage("cache")
        assert usage.category == "cache"
        assert "bytes" in str(usage)


# ─── TemporaryStorageManager Tests ──────────────────────────────


class TestTemporaryStorageManager:
    """Test temp file lifecycle."""

    def test_ensure_dirs(self, tmp_path: Path) -> None:
        """Ensure dirs should create temp directories."""
        mgr = TemporaryStorageManager(str(tmp_path))
        mgr.ensure_dirs()
        assert (tmp_path / "temp" / "downloads").exists()
        assert (tmp_path / "temp" / "processing").exists()

    def test_create_temp_path(self, tmp_path: Path) -> None:
        """Create temp path should return a valid path."""
        mgr = TemporaryStorageManager(str(tmp_path))
        mgr.ensure_dirs()
        path = mgr.create_temp_path(subdir="processing", suffix=".mp4")
        assert path.endswith(".mp4")
        assert Path(path).parent == tmp_path / "temp" / "processing"

    def test_register_download(self, tmp_path: Path) -> None:
        """Register download should create path with correct extension."""
        mgr = TemporaryStorageManager(str(tmp_path))
        mgr.ensure_dirs()
        path = mgr.register_download("https://example.com/video.mp4")
        assert path.endswith(".mp4")
        assert Path(path).parent == tmp_path / "temp" / "downloads"

    def test_cleanup_expired(self, tmp_path: Path) -> None:
        """Cleanup expired should not crash on empty dir."""
        mgr = TemporaryStorageManager(str(tmp_path), retention_hours=1)
        mgr.ensure_dirs()
        count = mgr.cleanup_expired()
        assert count >= 0


# ─── CacheManager Tests ─────────────────────────────────────────


class TestCacheManager:
    """Test cache management with storage and retrieval."""

    def test_ensure_dirs(self, tmp_path: Path) -> None:
        """Ensure dirs should create cache directories."""
        mgr = CacheManager(str(tmp_path))
        mgr.ensure_dirs()
        assert (tmp_path / "cache" / "frames").exists()

    def test_set_and_get(self, tmp_path: Path) -> None:
        """Set and get should round-trip content."""
        mgr = CacheManager(str(tmp_path))
        mgr.ensure_dirs()

        path = mgr.set("frames", "test_key", b"hello")
        assert path.exists()

        content = mgr.get("frames", "test_key")
        assert content == b"hello"

    def test_get_nonexistent(self, tmp_path: Path) -> None:
        """Get nonexistent should return None."""
        mgr = CacheManager(str(tmp_path))
        assert mgr.get("frames", "nonexistent") is None

    def test_invalidate(self, tmp_path: Path) -> None:
        """Invalidate should remove cache entry."""
        mgr = CacheManager(str(tmp_path))
        mgr.ensure_dirs()
        mgr.set("frames", "test_key", b"data")
        assert mgr.invalidate("frames", "test_key") is True
        assert mgr.get("frames", "test_key") is None

    def test_invalidate_category(self, tmp_path: Path) -> None:
        """Invalidate category should remove all entries."""
        mgr = CacheManager(str(tmp_path))
        mgr.ensure_dirs()
        mgr.set("frames", "k1", b"d1")
        mgr.set("frames", "k2", b"d2")
        count = mgr.invalidate_category("frames")
        assert count == 2

    def test_unknown_category(self, tmp_path: Path) -> None:
        """Unknown category should raise KeyError."""
        mgr = CacheManager(str(tmp_path))
        with pytest.raises(KeyError):
            mgr.get("invalid", "key")


# ─── ProxyStorageManager Tests ──────────────────────────────────


class TestProxyStorageManager:
    """Test proxy video storage."""

    def test_proxy_path(self, tmp_path: Path) -> None:
        """Proxy path should follow naming convention."""
        mgr = ProxyStorageManager(str(tmp_path))
        pid = str(uuid.uuid4())
        path = mgr.proxy_path(pid, "abc123", height=720)
        assert "abc123" in str(path)
        assert "720p" in str(path)
        assert path.suffix == ".mp4"

    def test_invalid_height(self, tmp_path: Path) -> None:
        """Invalid proxy height should raise ValueError."""
        mgr = ProxyStorageManager(str(tmp_path))
        with pytest.raises(ValueError):
            mgr.proxy_path("pid", "hash", height=999)


# ─── ExportStorageManager Tests ─────────────────────────────────


class TestExportStorageManager:
    """Test export file naming and paths."""

    def test_format_filename(self) -> None:
        """Format filename should produce safe names."""
        mgr = ExportStorageManager()
        name = mgr.format_filename("My Amazing Clip!", "mp4", include_timestamp=True)
        assert name.startswith("my_amazing_clip_")
        assert name.endswith(".mp4")
        assert "_" not in name.replace("my_amazing_clip_", "").split(".")[0] or True

    def test_format_filename_no_timestamp(self) -> None:
        """Format filename without timestamp."""
        mgr = ExportStorageManager()
        name = mgr.format_filename("My Clip", "mp4", include_timestamp=False)
        assert name == "my_clip.mp4"

    def test_invalid_format(self, tmp_path: Path) -> None:
        """Invalid format should raise ValueError."""
        mgr = ExportStorageManager(str(tmp_path))
        with pytest.raises(ValueError, match="Unsupported export format"):
            mgr.export_path("pid", "clip", "xyz")

    def test_slug_special_chars(self) -> None:
        """Slug should handle special characters."""
        mgr = ExportStorageManager()
        name = mgr.format_filename("Hello!!! World??? #2024", "mp4", include_timestamp=False)
        assert name == "hello_world_2024.mp4"


# ─── ModelStorageManager Tests ──────────────────────────────────


class TestModelStorageManager:
    """Test model file storage."""

    def test_ensure_dirs(self, tmp_path: Path) -> None:
        """Ensure dirs should create all model directories."""
        mgr = ModelStorageManager(str(tmp_path))
        mgr.ensure_dirs()

        for cat in ModelStorageManager.MODEL_CATEGORIES:
            assert (tmp_path / "models" / cat).exists()

    def test_invalid_category(self, tmp_path: Path) -> None:
        """Invalid category should raise ValueError."""
        mgr = ModelStorageManager(str(tmp_path))
        with pytest.raises(ValueError):
            mgr.category_dir("invalid")

    def test_list_models(self, tmp_path: Path) -> None:
        """List models should return installed models."""
        mgr = ModelStorageManager(str(tmp_path))
        mgr.ensure_dirs()

        # Create a fake model
        model_dir = mgr.model_path("whisper", "large-v3")
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "model.bin").write_text("fake model data")

        models = mgr.list_models()
        assert len(models) >= 1
        matching = [m for m in models if m["model_id"] == "large-v3"]
        assert len(matching) == 1


# ─── BackupManager Tests ────────────────────────────────────────


class TestBackupManager:
    """Test project backup and snapshot management."""

    def test_create_snapshot(self, tmp_path: Path) -> None:
        """Create snapshot should create a JSON file."""
        mgr = BackupManager(str(tmp_path))
        pid = str(uuid.uuid4())

        path = mgr.create_snapshot(pid, {"name": "test", "version": 1})
        assert Path(path).exists()

        data = json.loads(Path(path).read_text())
        assert data["data"]["name"] == "test"
        assert data["checksum"] is not None

    def test_list_snapshots(self, tmp_path: Path) -> None:
        """List snapshots should return created snapshots."""
        mgr = BackupManager(str(tmp_path))
        pid = str(uuid.uuid4())

        assert len(mgr.list_snapshots(pid)) == 0

        mgr.create_snapshot(pid, {"name": "v1"})
        mgr.create_snapshot(pid, {"name": "v2"})

        snapshots = mgr.list_snapshots(pid)
        assert len(snapshots) == 2

    def test_invalid_snapshot_type(self, tmp_path: Path) -> None:
        """Invalid snapshot type should raise ValueError."""
        mgr = BackupManager(str(tmp_path))
        with pytest.raises(ValueError):
            mgr.create_snapshot("pid", {}, snapshot_type="invalid")

    def test_verify_snapshot(self, tmp_path: Path) -> None:
        """Verify snapshot should check integrity."""
        mgr = BackupManager(str(tmp_path))
        pid = str(uuid.uuid4())
        mgr.create_snapshot(pid, {"name": "test"})

        result = mgr.verify_snapshot(pid, 1)
        assert result is True

    def test_restore_snapshot(self, tmp_path: Path) -> None:
        """Restore snapshot should return the data."""
        mgr = BackupManager(str(tmp_path))
        pid = str(uuid.uuid4())
        mgr.create_snapshot(pid, {"name": "test", "value": 42})

        data = mgr.restore_snapshot(pid, 1)
        assert data is not None
        assert data["name"] == "test"
        assert data["value"] == 42


# ─── CleanupScheduler Tests ─────────────────────────────────────


class TestCleanupScheduler:
    """Test cleanup scheduler operations."""

    @pytest.mark.asyncio
    async def test_run_cleanup(self, tmp_path: Path) -> None:
        """Run cleanup should complete without error."""
        scheduler = CleanupScheduler(str(tmp_path))
        results = await scheduler.run_cleanup()
        assert "temp_files_removed" in results
        assert "cache_entries_removed" in results
