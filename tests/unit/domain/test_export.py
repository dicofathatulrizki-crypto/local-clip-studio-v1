"""Unit tests for Export entity."""

from __future__ import annotations

import pytest

from backend.domain.entities import Export
from backend.domain.exceptions import DomainValidationError, InvalidExportStateError
from backend.domain.state_machines import ExportState


class TestExportCreation:
    def test_create_default(self) -> None:
        export = Export()
        assert export.id != ""
        assert export.format == "mp4"
        assert export.status == ExportState.PENDING
        assert export.progress == 0.0

    def test_create_with_custom_id(self) -> None:
        export = Export(id="custom-id", clip_id="clip-1", format="mp4")
        assert export.id == "custom-id"
        assert export.clip_id == "clip-1"

    def test_create_all_fields(self) -> None:
        export = Export(
            clip_id="clip-1",
            format="mp4",
            preset="high",
            status=ExportState.PENDING,
            progress=0.0,
        )
        assert export.format == "mp4"
        assert export.preset == "high"

    def test_unsupported_format_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Export(format="avi")

    def test_invalid_progress_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Export(progress=1.5)

    def test_negative_progress_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Export(progress=-0.1)

    def test_invalid_preset_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Export(preset="ultra")


class TestExportStateTransitions:
    def test_start_rendering(self) -> None:
        export = Export()
        export.start_rendering()
        assert export.status == ExportState.RENDERING
        assert export.started_at is not None
        assert export.is_rendering

    def test_complete(self) -> None:
        export = Export()
        export.start_rendering()
        export.complete("/tmp/output.mp4")
        assert export.status == ExportState.COMPLETED
        assert export.progress == 1.0
        assert export.output_path == "/tmp/output.mp4"
        assert export.completed_at is not None
        assert export.is_completed

    def test_fail(self) -> None:
        export = Export()
        export.start_rendering()
        export.mark_failed("Encoding error")
        assert export.status == ExportState.FAILED
        assert export.error_message == "Encoding error"
        assert export.is_failed

    def test_cancel_pending(self) -> None:
        export = Export()
        export.cancel()
        assert export.status == ExportState.CANCELLED
        assert export.is_cancelled

    def test_cancel_rendering(self) -> None:
        export = Export()
        export.start_rendering()
        export.cancel()
        assert export.is_cancelled

    def test_invalid_complete_from_pending(self) -> None:
        export = Export()
        with pytest.raises(InvalidExportStateError):
            export.complete("/tmp/output.mp4")

    def test_invalid_restart_completed(self) -> None:
        export = Export()
        export.start_rendering()
        export.complete("/tmp/output.mp4")
        with pytest.raises(InvalidExportStateError):
            export.start_rendering()


class TestExportBehaviour:
    def test_update_progress(self) -> None:
        export = Export()
        export.update_progress(0.5)
        assert export.progress == 0.5

    def test_update_progress_invalid_raises(self) -> None:
        export = Export()
        with pytest.raises(DomainValidationError):
            export.update_progress(1.5)

    def test_export_id_alias(self) -> None:
        export = Export(id="exp-123")
        assert export.export_id == "exp-123"

    def test_progress_percent(self) -> None:
        export = Export()
        export.update_progress(0.75)
        assert export.progress_percent == 75

    def test_is_pending(self) -> None:
        assert Export().is_pending
