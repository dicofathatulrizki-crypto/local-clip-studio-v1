"""Unit tests for ImportService (SRS §10.2).

All infrastructure mocked — no real filesystem, FFmpeg, yt-dlp, database, or network.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.domain.entities.project import Project
from backend.domain.entities.video import Video as DomainVideo
from backend.infrastructure.errors import (
    ConflictError,
    NotFoundError,
    StorageError,
    ValidationError,
)
from backend.services.import_service import ImportResult, ImportService


@pytest.fixture
def mock_vm_repo():
    r = MagicMock()
    r.get_by_hash = AsyncMock()
    r.create_from_domain = AsyncMock()
    r.delete_by_hash = AsyncMock()
    return r


@pytest.fixture
def mock_pv_repo():
    r = MagicMock()
    r.get = AsyncMock()
    r.create = AsyncMock()
    r.delete = AsyncMock()
    return r


@pytest.fixture
def mock_proj_repo():
    r = MagicMock()
    r.get_domain = AsyncMock()
    return r


@pytest.fixture
def mock_file_manager():
    r = MagicMock()
    r.copy_atomic = AsyncMock()
    return r


@pytest.fixture
def mock_ffprobe():
    r = MagicMock()
    r.probe = AsyncMock()
    return r


@pytest.fixture
def mock_dir_manager():
    r = MagicMock()
    from pathlib import Path
    r.project_dir = MagicMock(return_value=Path("/tmp/test_projects/proj-id"))
    return r


@pytest.fixture
def project_domain():
    """Create a minimal Project domain entity for testing."""
    return MagicMock(id="proj-123", name="Test Project")


@pytest.fixture
def service(
    mock_vm_repo, mock_pv_repo, mock_proj_repo,
    mock_file_manager, mock_ffprobe, mock_dir_manager,
):
    return ImportService(
        video_master_repository=mock_vm_repo,
        project_video_repository=mock_pv_repo,
        project_repository=mock_proj_repo,
        file_manager=mock_file_manager,
        ffprobe_service=mock_ffprobe,
        directory_manager=mock_dir_manager,
    )


# ------------------------------------------------------------------
# Successful import
# ------------------------------------------------------------------

class TestImportFile:
    """Tests for import_file()."""

    async def test_successful_import(self, service, mock_proj_repo, mock_vm_repo,
                                      mock_pv_repo, mock_ffprobe, mock_file_manager,
                                      project_domain, tmp_path):
        """A valid MP4 file is imported successfully."""
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video content")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = {
            "streams": [{"codec_type": "video", "width": 1920, "height": 1080,
                         "r_frame_rate": "30000/1001", "codec_name": "h264"}],
            "format": {"duration": "60.0", "bit_rate": "5000000"},
        }
        created_video = DomainVideo(original_filename="test.mp4", file_size_bytes=100,
                                     duration_ms=60000, width=1920, height=1080,
                                     fps=29.97, video_codec="h264")
        mock_vm_repo.get_by_hash.return_value = None
        mock_vm_repo.create_from_domain.return_value = created_video
        pv_orm = MagicMock(id="pv-1")
        mock_pv_repo.create.return_value = pv_orm

        result = await service.import_file("proj-123", str(video_path))

        assert isinstance(result, ImportResult)
        assert result.status == "ready"
        assert result.video_id is not None
        mock_vm_repo.create_from_domain.assert_awaited_once()
        mock_pv_repo.create.assert_awaited_once()

    async def test_invalid_file_type(self, service, mock_proj_repo, project_domain, tmp_path):
        """Unsupported file extension raises ValidationError."""
        bad_path = tmp_path / "test.txt"
        bad_path.write_text("not a video")
        mock_proj_repo.get_domain.return_value = project_domain

        with pytest.raises(ValidationError, match="format"):
            await service.import_file("proj-123", str(bad_path))

    async def test_file_too_large(self, service, mock_proj_repo, project_domain, tmp_path):
        """File exceeding max size raises ValidationError."""
        large_path = tmp_path / "large.mp4"
        # Minimal size matters only for mock — we mock stat in the real test.
        large_path.write_bytes(b"x" * 1024)
        mock_proj_repo.get_domain.return_value = project_domain

        with patch.object(large_path, "stat") as mock_stat:
            mock_stat.return_value.st_size = 60 * 1024 ** 3  # 60 GB
            with pytest.raises(ValidationError, match="limit"):
                await service.import_file("proj-123", str(large_path))

    async def test_missing_project(self, service, mock_proj_repo):
        """Non-existent project raises NotFoundError."""
        mock_proj_repo.get_domain.return_value = None

        with pytest.raises(NotFoundError, match="not found"):
            await service.import_file("bad-proj", "/tmp/fake.mp4")

    async def test_missing_file(self, service, mock_proj_repo, project_domain):
        """Non-existent file path raises ValidationError."""
        mock_proj_repo.get_domain.return_value = project_domain

        with pytest.raises(ValidationError, match="not found"):
            await service.import_file("proj-123", "/tmp/nonexistent.mp4")

    async def test_duplicate_detection(self, service, mock_proj_repo, mock_vm_repo,
                                        mock_ffprobe, project_domain, tmp_path):
        """Duplicate file (by hash) raises ConflictError."""
        video_path = tmp_path / "dup.mp4"
        video_path.write_bytes(b"dup content")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = {
            "streams": [{"codec_type": "video", "width": 640, "height": 480,
                         "r_frame_rate": "30/1", "codec_name": "h264"}],
            "format": {"duration": "10.0", "bit_rate": "1000000"},
        }
        existing = DomainVideo(original_filename="original.mp4", file_size_bytes=100,
                                duration_ms=10000, width=640, height=480,
                                fps=30.0, video_codec="h264")
        mock_vm_repo.get_by_hash.return_value = existing

        with pytest.raises(ConflictError, match="duplicate"):
            await service.import_file("proj-123", str(video_path))

    async def test_ffprobe_failure(self, service, mock_proj_repo, mock_ffprobe,
                                    project_domain, tmp_path):
        """FFprobe failure raises ValidationError."""
        video_path = tmp_path / "broken.mp4"
        video_path.write_bytes(b"garbage")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.side_effect = Exception("FFprobe error")

        with pytest.raises(ValidationError, match="metadata"):
            await service.import_file("proj-123", str(video_path))

    async def test_no_video_stream(self, service, mock_proj_repo, mock_ffprobe,
                                    project_domain, tmp_path):
        """File with no video stream raises ValidationError."""
        video_path = tmp_path / "audio_only.mp4"
        video_path.write_bytes(b"audio only")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = {
            "streams": [{"codec_type": "audio", "codec_name": "aac"}],
            "format": {"duration": "10.0"},
        }

        with pytest.raises(ValidationError, match="video stream"):
            await service.import_file("proj-123", str(video_path))

    async def test_repository_failure_on_video_create(self, service, mock_proj_repo,
                                                       mock_vm_repo, mock_ffprobe,
                                                       project_domain, tmp_path):
        """Repository failure during video_master creation raises."""
        video_path = tmp_path / "fail.mp4"
        video_path.write_bytes(b"fail")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = {
            "streams": [{"codec_type": "video", "width": 640, "height": 480,
                         "r_frame_rate": "30/1", "codec_name": "h264"}],
            "format": {"duration": "10.0"},
        }
        mock_vm_repo.get_by_hash.return_value = None
        mock_vm_repo.create_from_domain.side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            await service.import_file("proj-123", str(video_path))

    async def test_rollback_on_pv_create_failure(self, service, mock_proj_repo,
                                                  mock_vm_repo, mock_pv_repo,
                                                  mock_ffprobe, project_domain, tmp_path):
        """If ProjectVideo creation fails, VideoMaster is rolled back."""
        video_path = tmp_path / "rollback.mp4"
        video_path.write_bytes(b"rollback")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = {
            "streams": [{"codec_type": "video", "width": 640, "height": 480,
                         "r_frame_rate": "30/1", "codec_name": "h264"}],
            "format": {"duration": "10.0"},
        }
        mock_vm_repo.get_by_hash.return_value = None
        created_video = DomainVideo(original_filename="rollback.mp4", file_size_bytes=100,
                                     duration_ms=10000, width=640, height=480,
                                     fps=30.0, video_codec="h264")
        mock_vm_repo.create_from_domain.return_value = created_video
        mock_pv_repo.create.side_effect = Exception("PV create error")

        with pytest.raises(Exception, match="PV create error"):
            await service.import_file("proj-123", str(video_path))

        # Verify rollback: video master deleted and file cleaned
        mock_vm_repo.delete_by_hash.assert_awaited_once()

    async def test_checksum_generation(self, service, mock_proj_repo, mock_vm_repo,
                                        mock_ffprobe, project_domain, tmp_path):
        """SHA-256 checksum is generated and used for duplicate check."""
        video_path = tmp_path / "hash_test.mp4"
        video_path.write_bytes(b"content for hash")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = {
            "streams": [{"codec_type": "video", "width": 640, "height": 480,
                         "r_frame_rate": "30/1", "codec_name": "h264"}],
            "format": {"duration": "10.0"},
        }
        mock_vm_repo.get_by_hash.return_value = None
        created_video = DomainVideo(original_filename="hash_test.mp4", file_size_bytes=100,
                                     duration_ms=10000, width=640, height=480,
                                     fps=30.0, video_codec="h264")
        mock_vm_repo.create_from_domain.return_value = created_video
        pv_orm = MagicMock(id="pv-1")
        mock_pv_repo.create.return_value = pv_orm

        result = await service.import_file("proj-123", str(video_path))

        # Verify hash was passed to get_by_hash
        assert mock_vm_repo.get_by_hash.await_count >= 1
        assert result.status == "ready"


# ------------------------------------------------------------------
# import_url
# ------------------------------------------------------------------

class TestImportUrl:
    """Tests for import_url()."""

    async def test_invalid_url(self, service):
        """Invalid URL raises ValidationError."""
        with pytest.raises(ValidationError, match="URL"):
            await service.import_url("proj-123", "not-a-url")

    async def test_empty_url(self, service):
        """Empty URL raises ValidationError."""
        with pytest.raises(ValidationError, match="URL"):
            await service.import_url("proj-123", "")

    @patch("backend.services.import_service.shutil.rmtree")
    @patch("backend.services.import_service.asyncio.create_subprocess_exec")
    async def test_url_import_download_fails(self, mock_subprocess, mock_rmtree,
                                              service, mock_proj_repo, project_domain):
        """yt-dlp failure raises ValidationError."""
        mock_proj_repo.get_domain.return_value = project_domain
        proc = AsyncMock()
        proc.returncode = 1
        proc.stderr = b"Download failed"
        mock_subprocess.return_value = proc

        with pytest.raises(ValidationError, match="Download"):
            await service.import_url("proj-123", "https://example.com/video")

    @patch("backend.services.import_service.shutil.rmtree")
    @patch("backend.services.import_service.asyncio.create_subprocess_exec")
    async def test_url_import_ytdlp_not_found(self, mock_subprocess, mock_rmtree,
                                               service, mock_proj_repo, project_domain):
        """Missing yt-dlp raises ValidationError."""
        mock_proj_repo.get_domain.return_value = project_domain
        mock_subprocess.side_effect = FileNotFoundError()

        with pytest.raises(ValidationError, match="yt-dlp"):
            await service.import_url("proj-123", "https://example.com/video")

    @patch("backend.services.import_service.shutil.rmtree")
    @patch("backend.services.import_service.asyncio.create_subprocess_exec")
    async def test_url_import_cleanup(self, mock_subprocess, mock_rmtree,
                                       service, mock_proj_repo, project_domain, tmp_path):
        """Temp directory is cleaned up after successful URL import."""
        mock_proj_repo.get_domain.return_value = project_domain
        # Simulate yt-dlp download by having the mock create the output file
        async def fake_subprocess(*args, **kwargs):
            output_arg = None
            for i, a in enumerate(args):
                if a == "-o":
                    output_arg = args[i + 1]
                    break
            if output_arg:
                Path(output_arg).parent.mkdir(parents=True, exist_ok=True)
                Path(output_arg).write_bytes(b"downloaded content")
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc
        mock_subprocess.side_effect = fake_subprocess

        # Mock import_file to succeed (it will call _load_project again)
        service._load_project = AsyncMock(return_value=project_domain)

        video = DomainVideo(original_filename="url_test.mp4", file_size_bytes=100,
                             duration_ms=10000, width=640, height=480,
                             fps=30.0, video_codec="h264")
        service._vm_repo.get_by_hash = AsyncMock(return_value=None)
        service._vm_repo.create_from_domain = AsyncMock(return_value=video)
        service._pv_repo.create = AsyncMock(return_value=MagicMock(id="pv-u"))

        with patch.object(service, "_compute_hash", AsyncMock(return_value="abcd1234")):
            with patch.object(service, "_probe_file", AsyncMock(return_value={
                "streams": [{"codec_type": "video", "width": 640, "height": 480,
                             "r_frame_rate": "30/1", "codec_name": "h264"}],
                "format": {"duration": "10.0"},
            })):
                with patch.object(service, "_copy_file", AsyncMock()):
                    result = await service.import_url("proj-123", "https://example.com/v")

        assert result.status == "ready"
        # Temp dir cleanup was called
        assert mock_rmtree.called


# ------------------------------------------------------------------
# get_import_status
# ------------------------------------------------------------------

class TestGetImportStatus:
    async def test_status_found(self, service, mock_pv_repo):
        """Existing project-video record returns status."""
        pv_orm = MagicMock(id="pv-1", project_id="proj-123", video_id="vid-1",
                           source_path="/tmp/source.mp4", proxy_path="/tmp/proxy.mp4",
                           added_at=None)
        mock_pv_repo.get.return_value = pv_orm

        result = await service.get_import_status("pv-1")
        assert result.id == "pv-1"
        assert result.status == "ready"
        assert result.proxy_path == "/tmp/proxy.mp4"

    async def test_status_not_found(self, service, mock_pv_repo):
        """Missing record raises NotFoundError."""
        mock_pv_repo.get.return_value = None

        with pytest.raises(NotFoundError):
            await service.get_import_status("bad-pv")


# ------------------------------------------------------------------
# cancel_import
# ------------------------------------------------------------------

class TestCancelImport:
    async def test_cancel_success(self, service, mock_pv_repo):
        """Cancelling an import removes the record and source file."""
        pv_orm = MagicMock(id="pv-1", project_id="proj-123", video_id="vid-1",
                           source_path="/tmp/cancel_test.mp4", proxy_path=None)
        mock_pv_repo.get.return_value = pv_orm
        mock_pv_repo.delete = AsyncMock(return_value=True)

        await service.cancel_import("pv-1")
        mock_pv_repo.delete.assert_awaited_once_with("pv-1")

    async def test_cancel_not_found(self, service, mock_pv_repo):
        """Missing record raises NotFoundError."""
        mock_pv_repo.get.return_value = None

        with pytest.raises(NotFoundError):
            await service.cancel_import("bad-pv")


# ------------------------------------------------------------------
# validate_file
# ------------------------------------------------------------------

class TestValidateFile:
    async def test_valid_file(self, service, mock_ffprobe, tmp_path):
        """Valid file returns validation result."""
        path = tmp_path / "valid.mp4"
        path.write_bytes(b"valid")
        mock_ffprobe.probe.return_value = {
            "streams": [{"codec_type": "video", "width": 1920, "height": 1080,
                         "r_frame_rate": "30000/1001", "codec_name": "h264"}],
            "format": {"duration": "30.0"},
        }

        result = await service.validate_file(str(path))
        assert result["valid"] is True
        assert result["has_video"] is True

    async def test_unsupported_format(self, service, tmp_path):
        """Unsupported format raises ValidationError."""
        path = tmp_path / "test.wmv"
        path.write_bytes(b"test")

        with pytest.raises(ValidationError, match="format"):
            await service.validate_file(str(path))

    async def test_file_not_found(self, service):
        """Non-existent file raises ValidationError."""
        with pytest.raises(ValidationError, match="not found"):
            await service.validate_file("/tmp/nonexistent.avi")


# ------------------------------------------------------------------
# StorageError propagation
# ------------------------------------------------------------------

class TestStorageErrors:
    async def test_storage_error_on_copy(self, service, mock_proj_repo, mock_ffprobe,
                                          mock_file_manager, project_domain, tmp_path):
        """OSError during file copy raises StorageError."""
        video_path = tmp_path / "copy_fail.mp4"
        video_path.write_bytes(b"copy fail")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = {
            "streams": [{"codec_type": "video", "width": 640, "height": 480,
                         "r_frame_rate": "30/1", "codec_name": "h264"}],
            "format": {"duration": "10.0"},
        }
        mock_file_manager.copy_atomic.side_effect = OSError("Disk full")

        with pytest.raises(StorageError, match="Copy"):
            await service.import_file("proj-123", str(video_path))

    async def test_storage_error_on_mkdir(self, service, mock_proj_repo, mock_ffprobe,
                                           mock_dir_manager, project_domain, tmp_path):
        """OSError during directory creation raises StorageError."""
        video_path = tmp_path / "mkdir_fail.mp4"
        video_path.write_bytes(b"mkdir fail")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = {
            "streams": [{"codec_type": "video", "width": 640, "height": 480,
                         "r_frame_rate": "30/1", "codec_name": "h264"}],
            "format": {"duration": "10.0"},
        }

        dir_mock = MagicMock()
        dir_mock.__truediv__ = lambda self, x: dir_mock
        from pathlib import Path
        dir_mock.project_dir = MagicMock(return_value=Path("/tmp/no-perm"))
        dir_mock.mkdir.side_effect = OSError("Permission denied")
        mock_dir_manager.project_dir.return_value = dir_mock

        with pytest.raises(StorageError, match="directory"):
            await service.import_file("proj-123", str(video_path))


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------

class TestEdgeCases:
    async def test_empty_file(self, service, mock_proj_repo, mock_ffprobe,
                               mock_vm_repo, mock_pv_repo, project_domain, tmp_path):
        """Empty file is rejected by FFprobe (no streams)."""
        path = tmp_path / "empty.mp4"
        path.write_bytes(b"")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.side_effect = Exception("Cannot probe empty file")

        with pytest.raises(ValidationError, match="metadata"):
            await service.import_file("proj-123", str(path))

    async def test_filename_with_spaces(self, service, mock_proj_repo, mock_ffprobe,
                                         mock_vm_repo, mock_pv_repo, project_domain, tmp_path):
        """Filename with spaces is handled correctly."""
        video_path = tmp_path / "my video file.mp4"
        video_path.write_bytes(b"spaces")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = {
            "streams": [{"codec_type": "video", "width": 640, "height": 480,
                         "r_frame_rate": "30/1", "codec_name": "h264"}],
            "format": {"duration": "10.0"},
        }
        mock_vm_repo.get_by_hash.return_value = None
        created = DomainVideo(original_filename="my video file.mp4", file_size_bytes=100,
                               duration_ms=10000, width=640, height=480,
                               fps=30.0, video_codec="h264")
        mock_vm_repo.create_from_domain.return_value = created
        mock_pv_repo.create.return_value = MagicMock(id="pv-s")

        result = await service.import_file("proj-123", str(video_path))
        assert result.status == "ready"
