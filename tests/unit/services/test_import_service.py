"""Unit tests for ImportService (SRS §10.2).

All infrastructure mocked — no real filesystem, FFmpeg, yt-dlp, database, or network.
"""

from __future__ import annotations

from pathlib import Path
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
from backend.infrastructure.ffmpeg.types import MediaInfo, MediaStreamInfo
from backend.services.import_service import ImportResult, ImportService


@pytest.fixture
def mock_vm_repo():
    r = MagicMock()
    r.get_by_hash = AsyncMock(return_value=None)
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
    r.probe = MagicMock()  # sync callable — wrapped in asyncio.to_thread by _probe_file
    return r


@pytest.fixture
def mock_dir_manager():
    r = MagicMock()
    r.project_dir = MagicMock(return_value=Path("/tmp/test_projects/proj-id"))
    return r


@pytest.fixture
def project_domain():
    return MagicMock(id="proj-123", name="Test Project")


@pytest.fixture
def service( mock_vm_repo, mock_pv_repo, mock_proj_repo, mock_file_manager, mock_ffprobe, mock_dir_manager ):
    return ImportService(
        video_master_repository=mock_vm_repo,
        project_video_repository=mock_pv_repo,
        project_repository=mock_proj_repo,
        file_manager=mock_file_manager,
        ffprobe_service=mock_ffprobe,
        directory_manager=mock_dir_manager,
    )


def _make_stream(**kwargs) -> MediaStreamInfo:
    return MediaStreamInfo(
        index=0,
        codec_type=kwargs.get("codec_type", "video"),
        codec=kwargs.get("codec_name", "h264"),
        codec_long="",
        width=kwargs.get("width", 640),
        height=kwargs.get("height", 480),
        fps=kwargs.get("fps", 30.0),
        bitrate=kwargs.get("bitrate", 1000000),
        duration_ms=int(float(kwargs.get("duration", "10.0")) * 1000),
    )


def _probe_response(width=640, height=480, fps=30.0, codec="h264", duration="10.0", bitrate="1000000"):
    return MediaInfo(
        path="",
        file_size_bytes=0,
        duration_ms=int(float(duration) * 1000),
        bitrate=int(bitrate),
        format_name="mp4",
        video_streams=[_make_stream(
            codec_type="video", codec_name=codec,
            width=width, height=height, fps=fps,
            duration=duration,
        )],
        audio_streams=[_make_stream(
            codec_type="audio", codec_name="aac",
            bitrate=128000, duration=duration,
        )],
    )


# ==================================================================
# TestImportFile
# ==================================================================

class TestImportFile:

    async def test_successful_import(self, service, mock_proj_repo, mock_vm_repo,
                                      mock_pv_repo, mock_ffprobe, project_domain, tmp_path):
        path = tmp_path / "test.mp4"
        path.write_bytes(b"video data")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = _probe_response(width=1920, height=1080)
        created = DomainVideo(original_filename="test.mp4", file_size_bytes=100,
                               duration_ms=60000, width=1920, height=1080,
                               fps=29.97, video_codec="h264")
        mock_vm_repo.create_from_domain.return_value = created
        mock_pv_repo.create.return_value = MagicMock(id="pv-1")

        result = await service.import_file("proj-123", str(path))

        assert isinstance(result, ImportResult)
        assert result.status == "ready"
        mock_vm_repo.create_from_domain.assert_awaited_once()
        mock_pv_repo.create.assert_awaited_once()

    async def test_invalid_file_type(self, service, mock_proj_repo, project_domain, tmp_path):
        mock_proj_repo.get_domain.return_value = project_domain
        bad = tmp_path / "test.txt"
        bad.write_text("x")
        with pytest.raises(ValidationError, match="format"):
            await service.import_file("proj-123", str(bad))

    async def test_file_too_large(self, mock_vm_repo, mock_pv_repo, mock_proj_repo,
                                      mock_file_manager, mock_ffprobe, mock_dir_manager,
                                      project_domain, tmp_path):
        """File exceeding max size raises ValidationError."""
        mock_proj_repo.get_domain.return_value = project_domain
        svc = ImportService(mock_vm_repo, mock_pv_repo, mock_proj_repo,
                            mock_file_manager, mock_ffprobe, mock_dir_manager,
                            max_file_size=100)  # 100 byte limit
        path = tmp_path / "big.mp4"
        path.write_bytes(b"x" * 200)  # 200 bytes > 100 byte limit
        with pytest.raises(ValidationError, match="limit"):
            await svc.import_file("proj-123", str(path))

    async def test_missing_project(self, service, mock_proj_repo):
        mock_proj_repo.get_domain.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            await service.import_file("bad", "/tmp/f.mp4")

    async def test_missing_file(self, service, mock_proj_repo, project_domain):
        mock_proj_repo.get_domain.return_value = project_domain
        with pytest.raises(ValidationError, match="not found"):
            await service.import_file("proj-123", "/tmp/nope.mp4")

    async def test_duplicate_detection(self, service, mock_proj_repo, mock_vm_repo, mock_ffprobe, project_domain, tmp_path):
        path = tmp_path / "dup.mp4"
        path.write_bytes(b"dup")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = _probe_response()
        existing = DomainVideo(original_filename="orig.mp4", file_size_bytes=100,
                                duration_ms=10000, width=640, height=480,
                                fps=30.0, video_codec="h264")
        mock_vm_repo.get_by_hash.return_value = existing

        with pytest.raises(ConflictError, match="Duplicate"):
            await service.import_file("proj-123", str(path))

    async def test_ffprobe_failure(self, service, mock_proj_repo, mock_ffprobe, project_domain, tmp_path):
        path = tmp_path / "bad.mp4"
        path.write_bytes(b"bad")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.side_effect = Exception("Probe error")
        with pytest.raises(ValidationError, match="metadata"):
            await service.import_file("proj-123", str(path))

    async def test_no_video_stream(self, service, mock_proj_repo, mock_ffprobe, project_domain, tmp_path):
        path = tmp_path / "audio.mp4"
        path.write_bytes(b"audio")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = MediaInfo(
            path="",
            video_streams=[],
            audio_streams=[_make_stream(codec_type="audio", codec_name="aac")],
        )
        with pytest.raises(ValidationError, match="video stream"):
            await service.import_file("proj-123", str(path))

    async def test_repository_failure_on_video_create(self, service, mock_proj_repo, mock_vm_repo, mock_ffprobe, project_domain, tmp_path):
        path = tmp_path / "fail.mp4"
        path.write_bytes(b"fail")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = _probe_response()
        mock_vm_repo.create_from_domain.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            await service.import_file("proj-123", str(path))

    async def test_rollback_on_pv_create_failure(self, service, mock_proj_repo, mock_vm_repo, mock_pv_repo, mock_ffprobe, project_domain, tmp_path):
        path = tmp_path / "rb.mp4"
        path.write_bytes(b"rb")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = _probe_response()
        created = DomainVideo(original_filename="rb.mp4", file_size_bytes=100,
                               duration_ms=10000, width=640, height=480,
                               fps=30.0, video_codec="h264")
        mock_vm_repo.create_from_domain.return_value = created
        mock_pv_repo.create.side_effect = Exception("PV error")

        with pytest.raises(Exception, match="PV error"):
            await service.import_file("proj-123", str(path))
        mock_vm_repo.delete_by_hash.assert_awaited_once()

    async def test_checksum_generation(self, service, mock_proj_repo, mock_vm_repo, mock_ffprobe, mock_pv_repo, project_domain, tmp_path):
        path = tmp_path / "hash_test.mp4"
        path.write_bytes(b"hash content")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = _probe_response()
        created = DomainVideo(original_filename="hash_test.mp4", file_size_bytes=100,
                               duration_ms=10000, width=640, height=480,
                               fps=30.0, video_codec="h264")
        mock_vm_repo.create_from_domain.return_value = created
        mock_pv_repo.create.return_value = MagicMock(id="pv-h")

        result = await service.import_file("proj-123", str(path))
        assert mock_vm_repo.get_by_hash.await_count >= 1
        assert result.status == "ready"


# ==================================================================
# TestImportUrl
# ==================================================================

class TestImportUrl:

    async def test_invalid_url(self, service):
        with pytest.raises(ValidationError, match="URL"):
            await service.import_url("proj-123", "not-a-url")

    async def test_empty_url(self, service):
        with pytest.raises(ValidationError, match="URL"):
            await service.import_url("proj-123", "")

    @patch("backend.services.import_service.asyncio.create_subprocess_exec")
    async def test_url_import_download_fails(self, mock_sub, service):
        proc = AsyncMock()
        proc.returncode = 1
        proc.stderr = b"yt-dlp error"
        proc.communicate = AsyncMock(return_value=(b"", b"yt-dlp error"))
        mock_sub.return_value = proc

        with pytest.raises(ValidationError, match="Download"):
            await service.import_url("proj-123", "https://example.com/v")

    @patch("backend.services.import_service.asyncio.create_subprocess_exec")
    async def test_url_import_ytdlp_not_found(self, mock_sub, service):
        mock_sub.side_effect = FileNotFoundError()
        with pytest.raises(ValidationError, match="yt-dlp"):
            await service.import_url("proj-123", "https://example.com/v")


# ==================================================================
# TestGetImportStatus
# ==================================================================

class TestGetImportStatus:

    async def test_status_found(self, service, mock_pv_repo):
        pv = MagicMock(id="pv-1", project_id="proj-123", video_id="vid-1",
                       source_path="/tmp/s.mp4", proxy_path="/tmp/p.mp4", added_at=None)
        mock_pv_repo.get.return_value = pv
        r = await service.get_import_status("pv-1")
        assert r.id == "pv-1"
        assert r.status == "ready"

    async def test_status_not_found(self, service, mock_pv_repo):
        mock_pv_repo.get.return_value = None
        with pytest.raises(NotFoundError):
            await service.get_import_status("bad")


# ==================================================================
# TestCancelImport
# ==================================================================

class TestCancelImport:

    async def test_cancel_success(self, service, mock_pv_repo):
        pv = MagicMock(id="pv-1", project_id="proj-123", video_id="vid-1", source_path="/tmp/c.mp4")
        mock_pv_repo.get.return_value = pv
        mock_pv_repo.delete = AsyncMock(return_value=True)
        await service.cancel_import("pv-1")
        mock_pv_repo.delete.assert_awaited_once_with("pv-1")

    async def test_cancel_not_found(self, service, mock_pv_repo):
        mock_pv_repo.get.return_value = None
        with pytest.raises(NotFoundError):
            await service.cancel_import("bad")


# ==================================================================
# TestValidateFile
# ==================================================================

class TestValidateFile:

    async def test_valid_file(self, service, mock_ffprobe, tmp_path):
        p = tmp_path / "v.mp4"
        p.write_bytes(b"x")
        mock_ffprobe.probe.return_value = _probe_response()
        r = await service.validate_file(str(p))
        assert r["valid"] is True

    async def test_unsupported_format(self, service, tmp_path):
        p = tmp_path / "t.wmv"
        p.write_bytes(b"x")
        with pytest.raises(ValidationError, match="format"):
            await service.validate_file(str(p))

    async def test_file_not_found(self, service):
        with pytest.raises(ValidationError, match="not found"):
            await service.validate_file("/tmp/nope.avi")


# ==================================================================
# TestStorageErrors
# ==================================================================

class TestStorageErrors:

    async def test_storage_error_on_copy(self, service, mock_proj_repo, mock_ffprobe, mock_file_manager, project_domain, tmp_path):
        path = tmp_path / "cf.mp4"
        path.write_bytes(b"cf")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = _probe_response()
        mock_file_manager.copy_atomic.side_effect = OSError("Disk full")
        with pytest.raises(StorageError, match="Copy"):
            await service.import_file("proj-123", str(path))

    async def test_storage_error_on_mkdir(self, service, mock_proj_repo, mock_ffprobe, mock_dir_manager, project_domain, tmp_path):
        """_storage_path mkdir OSError → StorageError."""
        path = tmp_path / "mk.mp4"
        path.write_bytes(b"mk")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = _probe_response()

        pd = MagicMock(spec=Path)
        pd.__truediv__ = lambda self, x: pd
        pd.mkdir = MagicMock(side_effect=OSError("Permission denied"))
        mock_dir_manager.project_dir.return_value = pd

        with pytest.raises(StorageError, match="directory"):
            await service.import_file("proj-123", str(path))


# ==================================================================
# TestEdgeCases
# ==================================================================

class TestEdgeCases:

    async def test_empty_file(self, service, mock_proj_repo, mock_ffprobe, project_domain, tmp_path):
        path = tmp_path / "empty.mp4"
        path.write_bytes(b"")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.side_effect = Exception("Cannot probe")
        with pytest.raises(ValidationError, match="metadata"):
            await service.import_file("proj-123", str(path))

    async def test_filename_with_spaces(self, service, mock_proj_repo, mock_vm_repo, mock_pv_repo, mock_ffprobe, project_domain, tmp_path):
        path = tmp_path / "my video.mp4"
        path.write_bytes(b"spaces")
        mock_proj_repo.get_domain.return_value = project_domain
        mock_ffprobe.probe.return_value = _probe_response()
        created = DomainVideo(original_filename="my video.mp4", file_size_bytes=100,
                               duration_ms=10000, width=640, height=480,
                               fps=30.0, video_codec="h264")
        mock_vm_repo.create_from_domain.return_value = created
        mock_pv_repo.create.return_value = MagicMock(id="pv-s")
        r = await service.import_file("proj-123", str(path))
        assert r.status == "ready"
