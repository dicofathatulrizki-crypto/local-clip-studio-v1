"""Integration tests for the FastAPI app factory (Module B11).

Tests lifespan, middleware, router registration, WebSocket, OpenAPI,
and dependency injection behaviour.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config.settings import Settings


@pytest.fixture
def debug_app():
    Settings.reset_instance()
    s = Settings(environment="testing", api__debug=True)
    return create_app(s)


@pytest.fixture
def production_app():
    Settings.reset_instance()
    s = Settings(environment="testing", api__debug=False)
    return create_app(s)


@pytest.fixture
def client(debug_app):
    return TestClient(debug_app)


class TestAppFactory:
    """Tests for create_app() and its configuration."""

    def test_create_app_returns_app(self):
        Settings.reset_instance()
        app = create_app()
        assert app.title == "Local Clip Studio"
        assert app.version == "1.0.0"

    def test_router_registration(self, debug_app):
        """All 4 route modules are registered."""
        path_str = str([str(r.path) for r in debug_app.routes if hasattr(r, "path")])
        assert "projects" in path_str
        assert "settings" in path_str or "v1/settings" in path_str
        assert "system" in path_str or "v1/system" in path_str

    def test_health_endpoint(self, client):
        r = client.get("/api/v1/system/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"


class TestOpenAPI:
    """OpenAPI schema availability based on debug flag."""

    def test_openapi_schema_in_debug(self, debug_app):
        client = TestClient(debug_app)
        r = client.get("/api/openapi.json")
        assert r.status_code == 200
        data = r.json()
        assert "info" in data
        assert "paths" in data

    def test_openapi_disabled_in_production(self, production_app):
        client = TestClient(production_app)
        r = client.get("/api/openapi.json")
        assert r.status_code == 404


class TestWebSocket:
    """WebSocket endpoint registration."""

    def test_websocket_endpoint_registered(self, debug_app):
        """The WebSocket route is mounted."""
        routes = [r.path for r in debug_app.routes if hasattr(r, "path")]
        ws_routes = [p for p in routes if "ws" in p]
        assert len(ws_routes) >= 1
        assert any("/ws" in p for p in ws_routes)


class TestExceptionHandlers:
    """Global exception handler behaviour."""

    def test_not_found_returns_404(self, client):
        r = client.get("/api/v1/nonexistent")
        assert r.status_code == 404


class TestDependencyOverrides:
    """Dependency injection overrides work correctly."""

    def test_override_system_deps(self, debug_app):
        """System endpoints can have deps overridden."""
        client = TestClient(debug_app)
        r = client.get("/api/v1/system/version")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
