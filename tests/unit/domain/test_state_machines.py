"""Unit tests for domain state machines."""

from __future__ import annotations

import pytest

from backend.domain.exceptions import (
    InvalidExportStateError,
    InvalidPluginStateError,
    InvalidProjectStateError,
    InvalidVideoStateError,
)
from backend.domain.state_machines import (
    AnalysisState,
    ClipState,
    ExportState,
    PluginState,
    ProjectState,
    UploadState,
    is_valid_analysis_transition,
    is_valid_clip_transition,
    is_valid_export_transition,
    is_valid_plugin_transition,
    is_valid_project_transition,
    is_valid_upload_transition,
    valid_analysis_transitions,
    valid_plugin_transitions,
    valid_project_transitions,
    valid_upload_transitions,
    validate_analysis_transition,
    validate_clip_transition,
    validate_export_transition,
    validate_plugin_transition,
    validate_project_transition,
    validate_upload_transition,
)


class TestProjectState:
    def test_valid_transition_create_to_active(self) -> None:
        assert is_valid_project_transition(ProjectState.CREATED, ProjectState.ACTIVE)
        validate_project_transition(ProjectState.CREATED, ProjectState.ACTIVE)

    def test_valid_transition_create_to_deleted(self) -> None:
        assert is_valid_project_transition(ProjectState.CREATED, ProjectState.DELETED)

    def test_valid_transition_active_to_archived(self) -> None:
        assert is_valid_project_transition(ProjectState.ACTIVE, ProjectState.ARCHIVED)

    def test_valid_transition_archived_to_active(self) -> None:
        assert is_valid_project_transition(ProjectState.ARCHIVED, ProjectState.ACTIVE)

    def test_invalid_transition_created_to_archived(self) -> None:
        assert not is_valid_project_transition(ProjectState.CREATED, ProjectState.ARCHIVED)
        with pytest.raises(InvalidProjectStateError):
            validate_project_transition(ProjectState.CREATED, ProjectState.ARCHIVED)

    def test_invalid_transition_deleted_to_any(self) -> None:
        assert not is_valid_project_transition(ProjectState.DELETED, ProjectState.ACTIVE)
        with pytest.raises(InvalidProjectStateError):
            validate_project_transition(ProjectState.DELETED, ProjectState.ACTIVE)

    def test_valid_transitions_list(self) -> None:
        transitions = valid_project_transitions(ProjectState.CREATED)
        assert ProjectState.ACTIVE in transitions
        assert ProjectState.DELETED in transitions

    def test_deleted_terminal(self) -> None:
        assert valid_project_transitions(ProjectState.DELETED) == []


class TestUploadState:
    def test_pending_to_validating(self) -> None:
        assert is_valid_upload_transition(UploadState.PENDING, UploadState.VALIDATING)

    def test_pending_to_cancelled(self) -> None:
        assert is_valid_upload_transition(UploadState.PENDING, UploadState.CANCELLED)

    def test_validating_to_importing(self) -> None:
        assert is_valid_upload_transition(UploadState.VALIDATING, UploadState.IMPORTING)

    def test_validating_to_failed(self) -> None:
        assert is_valid_upload_transition(UploadState.VALIDATING, UploadState.FAILED)

    def test_importing_to_ready(self) -> None:
        assert is_valid_upload_transition(UploadState.IMPORTING, UploadState.READY)

    def test_importing_to_failed(self) -> None:
        assert is_valid_upload_transition(UploadState.IMPORTING, UploadState.FAILED)

    def test_ready_terminal(self) -> None:
        assert not is_valid_upload_transition(UploadState.READY, UploadState.PENDING)
        with pytest.raises(InvalidVideoStateError):
            validate_upload_transition(UploadState.READY, UploadState.PENDING)

    def test_cancelled_terminal(self) -> None:
        assert valid_upload_transitions(UploadState.CANCELLED) == []

    def test_invalid_skip_to_ready(self) -> None:
        assert not is_valid_upload_transition(UploadState.PENDING, UploadState.READY)


class TestAnalysisState:
    def test_queued_to_preprocessing(self) -> None:
        assert is_valid_analysis_transition(AnalysisState.QUEUED, AnalysisState.PREPROCESSING)
        validate_analysis_transition(AnalysisState.QUEUED, AnalysisState.PREPROCESSING)

    def test_queued_to_cancelled(self) -> None:
        assert is_valid_analysis_transition(AnalysisState.QUEUED, AnalysisState.CANCELLED)

    def test_preprocessing_to_transcribing(self) -> None:
        assert is_valid_analysis_transition(AnalysisState.PREPROCESSING, AnalysisState.TRANSCRIBING)

    def test_transcribing_to_diarizing(self) -> None:
        assert is_valid_analysis_transition(AnalysisState.TRANSCRIBING, AnalysisState.DIARIZING)

    def test_transcribing_to_scene_detecting(self) -> None:
        assert is_valid_analysis_transition(AnalysisState.TRANSCRIBING, AnalysisState.SCENE_DETECTING)

    def test_scoring_to_completed(self) -> None:
        assert is_valid_analysis_transition(AnalysisState.SCORING, AnalysisState.COMPLETED)

    def test_completed_terminal(self) -> None:
        assert not is_valid_analysis_transition(AnalysisState.COMPLETED, AnalysisState.QUEUED)
        with pytest.raises(InvalidVideoStateError):
            validate_analysis_transition(AnalysisState.COMPLETED, AnalysisState.QUEUED)

    def test_failed_terminal(self) -> None:
        assert valid_analysis_transitions(AnalysisState.FAILED) == []

    def test_cancelled_terminal(self) -> None:
        assert valid_analysis_transitions(AnalysisState.CANCELLED) == []

    def test_invalid_skip_stage(self) -> None:
        assert not is_valid_analysis_transition(AnalysisState.QUEUED, AnalysisState.SCORING)


class TestClipState:
    def test_candidate_to_accepted(self) -> None:
        assert is_valid_clip_transition(ClipState.CANDIDATE, ClipState.ACCEPTED)

    def test_candidate_to_rejected(self) -> None:
        assert is_valid_clip_transition(ClipState.CANDIDATE, ClipState.REJECTED)

    def test_candidate_to_modified(self) -> None:
        assert is_valid_clip_transition(ClipState.CANDIDATE, ClipState.MODIFIED)

    def test_accepted_to_modified(self) -> None:
        assert is_valid_clip_transition(ClipState.ACCEPTED, ClipState.MODIFIED)

    def test_accepted_to_rejected(self) -> None:
        assert is_valid_clip_transition(ClipState.ACCEPTED, ClipState.REJECTED)

    def test_rejected_to_accepted(self) -> None:
        assert is_valid_clip_transition(ClipState.REJECTED, ClipState.ACCEPTED)

    def test_modified_to_accepted(self) -> None:
        assert is_valid_clip_transition(ClipState.MODIFIED, ClipState.ACCEPTED)

    def test_invalid_transition(self) -> None:
        assert not is_valid_clip_transition(ClipState.REJECTED, ClipState.MODIFIED)
        from backend.domain.exceptions import InvalidClipRangeError

        with pytest.raises(InvalidClipRangeError):
            validate_clip_transition(ClipState.REJECTED, ClipState.MODIFIED)


class TestExportState:
    def test_pending_to_rendering(self) -> None:
        assert is_valid_export_transition(ExportState.PENDING, ExportState.RENDERING)
        validate_export_transition(ExportState.PENDING, ExportState.RENDERING)

    def test_pending_to_cancelled(self) -> None:
        assert is_valid_export_transition(ExportState.PENDING, ExportState.CANCELLED)

    def test_rendering_to_completed(self) -> None:
        assert is_valid_export_transition(ExportState.RENDERING, ExportState.COMPLETED)

    def test_rendering_to_failed(self) -> None:
        assert is_valid_export_transition(ExportState.RENDERING, ExportState.FAILED)

    def test_rendering_to_cancelled(self) -> None:
        assert is_valid_export_transition(ExportState.RENDERING, ExportState.CANCELLED)

    def test_completed_terminal(self) -> None:
        assert not is_valid_export_transition(ExportState.COMPLETED, ExportState.PENDING)
        with pytest.raises(InvalidExportStateError):
            validate_export_transition(ExportState.COMPLETED, ExportState.PENDING)

    def test_invalid_pending_to_completed(self) -> None:
        assert not is_valid_export_transition(ExportState.PENDING, ExportState.COMPLETED)


class TestPluginState:
    def test_discovered_to_loaded(self) -> None:
        assert is_valid_plugin_transition(PluginState.DISCOVERED, PluginState.LOADED)

    def test_discovered_to_disabled(self) -> None:
        assert is_valid_plugin_transition(PluginState.DISCOVERED, PluginState.DISABLED)

    def test_discovered_to_error(self) -> None:
        assert is_valid_plugin_transition(PluginState.DISCOVERED, PluginState.ERROR)

    def test_loaded_to_initialized(self) -> None:
        assert is_valid_plugin_transition(PluginState.LOADED, PluginState.INITIALIZED)

    def test_initialized_to_active(self) -> None:
        assert is_valid_plugin_transition(PluginState.INITIALIZED, PluginState.ACTIVE)

    def test_active_to_shutdown(self) -> None:
        assert is_valid_plugin_transition(PluginState.ACTIVE, PluginState.SHUTDOWN)

    def test_shutdown_to_disabled(self) -> None:
        assert is_valid_plugin_transition(PluginState.SHUTDOWN, PluginState.DISABLED)

    def test_shutdown_to_active(self) -> None:
        assert is_valid_plugin_transition(PluginState.SHUTDOWN, PluginState.ACTIVE)

    def test_error_to_shutdown(self) -> None:
        assert is_valid_plugin_transition(PluginState.ERROR, PluginState.SHUTDOWN)

    def test_error_to_initialized(self) -> None:
        assert is_valid_plugin_transition(PluginState.ERROR, PluginState.INITIALIZED)

    def test_disabled_terminal(self) -> None:
        assert valid_plugin_transitions(PluginState.DISABLED) == []

    def test_invalid_transition(self) -> None:
        assert not is_valid_plugin_transition(PluginState.DISCOVERED, PluginState.ACTIVE)
        with pytest.raises(InvalidPluginStateError):
            validate_plugin_transition(PluginState.DISCOVERED, PluginState.ACTIVE)
