"""Comprehensive API route tests for Module B10.

Uses FastAPI TestClient with dependency_overrides to mock all services.
No database, filesystem, FFmpeg, or real infrastructure.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import get_db_session
from backend.config.settings import Settings
from backend.infrastructure.errors import ConflictError, NotFoundError
from backend.main import create_app
from backend.services.import_service import ImportResult
from backend.services.plugin_service import PluginNotFoundError


# ── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def mock_project_service():
    s = MagicMock()
    mock_project = MagicMock(spec=["id", "name", "description", "created_at", "updated_at", "last_opened_at"])
    mock_project.id = "p1"
    mock_project.name = "Test"
    mock_project.description = "A project"
    mock_project.created_at = None
    mock_project.updated_at = None
    mock_project.last_opened_at = None
    s.create = AsyncMock(return_value=mock_project)
    s.get = AsyncMock(return_value=mock_project)
    s.list = AsyncMock(return_value=([mock_project], 1))
    s.update = AsyncMock(return_value=mock_project)
    s.delete = AsyncMock()
    s.archive = AsyncMock(return_value="/tmp/archive/path")
    s.restore = AsyncMock(return_value=mock_project)
    s.get_recent = AsyncMock(return_value=[mock_project])
    s.duplicate = AsyncMock(return_value=mock_project)
    return s

@pytest.fixture
def mock_import_service():
    s = MagicMock()
    s.import_file = AsyncMock(return_value=ImportResult(id="pv-1", video_id="vid-1", source_path="/tmp/p.mp4", status="ready"))
    s.import_url = AsyncMock(return_value=ImportResult(id="pv-2", video_id="vid-2", source_path="/tmp/u.mp4", status="ready"))
    s.get_import_status = AsyncMock(return_value=ImportResult(id="pv-1", video_id="vid-1", source_path="/tmp/p.mp4", status="ready"))
    s.cancel_import = AsyncMock()
    s.validate_file = AsyncMock(return_value={"valid": True, "filename": "test.mp4", "file_size_bytes": 100, "has_video": True, "has_audio": True})
    return s

@pytest.fixture
def mock_settings_service():
    s = MagicMock()
    s.get_all = AsyncMock(return_value={"theme": "dark", "language": "en"})
    s.get_category = AsyncMock(return_value={"theme": "dark"})
    s.get_setting = AsyncMock()
    s.update_settings = AsyncMock()
    s.set_setting = AsyncMock()
    s.reset_setting = AsyncMock()
    s.reset_category = AsyncMock()
    s.reset_all = AsyncMock()
    s.export_settings = AsyncMock(return_value='{"theme": "dark"}')
    s.import_settings = AsyncMock()
    return s

@pytest.fixture
def mock_provider_service():
    s = MagicMock()
    s.list_providers = AsyncMock(return_value=[])
    return s

@pytest.fixture
def mock_plugin_service():
    s = MagicMock()
    s.get_statistics = AsyncMock(return_value={"total": 3, "enabled": 2, "by_state": {"active": 2}})
    return s


@pytest.fixture
def app(mock_project_service, mock_import_service, mock_settings_service,
        mock_provider_service, mock_plugin_service):
    Settings.reset_instance()
    Settings(environment="testing")

    application = create_app()

    from backend.api.routes.projects import _get_service as _get_proj_svc
    from backend.api.routes.videos import _get_service as _get_import_svc
    from backend.api.routes.settings import _get_service as _get_settings_svc
    from backend.api.routes.system import _get_provider_service, _get_plugin_service

    application.dependency_overrides[_get_proj_svc] = lambda: mock_project_service
    application.dependency_overrides[_get_import_svc] = lambda: mock_import_service
    application.dependency_overrides[_get_settings_svc] = lambda: mock_settings_service
    application.dependency_overrides[_get_provider_service] = lambda: mock_provider_service
    application.dependency_overrides[_get_plugin_service] = lambda: mock_plugin_service
    # Override the db session dependency since we don't need it
    application.dependency_overrides[get_db_session] = lambda: None

    return application


@pytest.fixture
def client(app):
    return TestClient(app)


# ==================================================================
# PROJECT API TESTS
# ==================================================================

class TestProjectsAPI:
    BASE = "/api/v1/projects"

    def test_create_project(self, client):
        resp = client.post(self.BASE, json={"name": "Test", "description": "A project"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test"

    def test_create_project_empty_name(self, client, mock_project_service):
        mock_project_service.create.side_effect = Exception("ValidationError")
        resp = client.post(self.BASE, json={"name": ""})
        assert resp.status_code == 422

    def test_list_projects(self, client, mock_project_service):
        mock_project_service.list.return_value = ([], 0)
        resp = client.get(self.BASE)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] == 0

    def test_get_project(self, client):
        resp = client.get(f"{self.BASE}/p1")
        assert resp.status_code == 200

    def test_get_project_not_found(self, client, mock_project_service):
        mock_project_service.get.return_value = None
        resp = client.get(f"{self.BASE}/nonexistent")
        assert resp.status_code == 404

    def test_update_project(self, client):
        resp = client.patch(f"{self.BASE}/p1", json={"name": "Updated"})
        assert resp.status_code == 200

    def test_delete_project(self, client, mock_project_service):
        mock_project_service.delete = AsyncMock()
        resp = client.delete(f"{self.BASE}/p1")
        assert resp.status_code == 204

    def test_archive_project(self, client, mock_project_service):
        resp = client.post(f"{self.BASE}/p1/archive")
        assert resp.status_code == 200
        data = resp.json()
        assert data["archived"] is True
        assert "path" in data

    def test_restore_project(self, client):
        resp = client.post(f"{self.BASE}/p1/restore")
        assert resp.status_code == 200

    def test_duplicate_project(self, client):
        resp = client.post(f"{self.BASE}/p1/duplicate", json={"new_name": "Copy"})
        assert resp.status_code == 201

    def test_recent_projects(self, client, mock_project_service):
        mock_project_service.get_recent.return_value = []
        resp = client.get(f"{self.BASE}/recent")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_projects_pagination(self, client, mock_project_service):
        mock_project_service.list.return_value = ([], 0)
        resp = client.get(f"{self.BASE}?limit=5&offset=10")
        assert resp.status_code == 200
        mock_project_service.list.assert_called_with(limit=5, offset=10)

    def test_create_project_missing_name(self, client):
        resp = client.post(self.BASE, json={"description": "No name"})
        assert resp.status_code == 422

    def test_get_project_service_error(self, client, mock_project_service):
        mock_project_service.get.side_effect = Exception("Internal error")
        resp = client.get(f"{self.BASE}/p1")
        assert resp.status_code == 500


# ==================================================================
# VIDEO API TESTS
# ==================================================================

class TestVideosAPI:
    BASE = "/api/v1/projects/p1/videos"

    def test_validate_video(self, client, mock_import_service):
        resp = client.post(f"{self.BASE}/validate", files={"file": ("test.mp4", b"data", "video/mp4")})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True

    def test_import_status(self, client, mock_import_service):
        resp = client.get(f"{self.BASE}/pv-1/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "pv-1"

    def test_cancel_import(self, client, mock_import_service):
        resp = client.post(f"{self.BASE}/pv-1/cancel")
        assert resp.status_code == 204

    def test_import_url(self, client, mock_import_service):
        resp = client.post(f"{self.BASE}/import-url", json={"url": "https://example.com/video.mp4"})
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "ready"

    def test_validate_video_invalid_file(self, client, mock_import_service):
        resp = client.post(f"{self.BASE}/validate", files={"file": ("test.txt", b"x", "text/plain")})
        assert resp.status_code in (200, 422)

    def test_cancel_import_not_found(self, client, mock_import_service):
        mock_import_service.cancel_import.side_effect = NotFoundError(message="Not found", details={})
        resp = client.post(f"{self.BASE}/bad-id/cancel")
        assert resp.status_code == 404


# ==================================================================
# SETTINGS API TESTS
# ==================================================================

class TestSettingsAPI:
    BASE = "/api/v1/settings"

    def test_get_all(self, client, mock_settings_service):
        resp = client.get(self.BASE)
        assert resp.status_code == 200
        assert resp.json() == {"theme": "dark", "language": "en"}

    def test_get_category(self, client, mock_settings_service):
        resp = client.get(f"{self.BASE}/appearance")
        assert resp.status_code == 200
        assert resp.json() == {"theme": "dark"}

    def test_get_category_invalid(self, client, mock_settings_service):
        from backend.services.settings_service import SettingValidationError
        mock_settings_service.get_category.side_effect = SettingValidationError(message="Invalid category", details={})
        resp = client.get(f"{self.BASE}/invalid_cat")
        assert resp.status_code == 400

    def test_get_key(self, client, mock_settings_service):
        mock_settings_service.get_setting.return_value = "dark"
        resp = client.get(f"{self.BASE}/general/language")
        assert resp.status_code == 200
        assert resp.json()["value"] == "dark"

    def test_get_key_not_found(self, client, mock_settings_service):
        mock_settings_service.get_setting.return_value = None
        resp = client.get(f"{self.BASE}/general/nonexistent")
        assert resp.status_code == 404

    def test_update_settings(self, client, mock_settings_service):
        mock_settings_service.update_settings.return_value = {"theme": "light"}
        resp = client.patch(self.BASE, json={"settings": {"theme": "light"}})
        assert resp.status_code == 200

    def test_reset_setting(self, client, mock_settings_service):
        resp = client.delete(f"{self.BASE}/general/language")
        assert resp.status_code == 204

    def test_reset_category(self, client, mock_settings_service):
        resp = client.delete(f"{self.BASE}/general")
        assert resp.status_code == 204

    def test_export_settings(self, client, mock_settings_service):
        resp = client.post(f"{self.BASE}/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "settings" in data

    def test_import_settings(self, client, mock_settings_service):
        mock_settings_service.import_settings.return_value = {"theme": "dark"}
        resp = client.post(f"{self.BASE}/import", json={"settings": {"theme": "dark"}})
        assert resp.status_code == 200


# ==================================================================
# SYSTEM API TESTS
# ==================================================================

class TestSystemAPI:
    BASE = "/api/v1/system"

    def test_health(self, client):
        resp = client.get(f"{self.BASE}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_version(self, client):
        resp = client.get(f"{self.BASE}/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "app_name" in data

    def test_capabilities(self, client):
        resp = client.get(f"{self.BASE}/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert ".mp4" in data["supported_formats"]

    def test_storage(self, client, tmp_path):
        import os
        from backend.config.settings import Settings
        s = Settings.get_instance()
        orig = s.storage.base_path
        s.storage.base_path = str(tmp_path)
        try:
            resp = client.get(f"{self.BASE}/storage")
            assert resp.status_code == 200
            data = resp.json()
            assert "app_directory" in data
            assert "free_gb" in data
        finally:
            s.storage.base_path = orig

    def test_providers(self, client, mock_provider_service):
        resp = client.get(f"{self.BASE}/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "enabled" in data

    def test_plugins(self, client, mock_plugin_service):
        resp = client.get(f"{self.BASE}/plugins")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["active"] == 2
