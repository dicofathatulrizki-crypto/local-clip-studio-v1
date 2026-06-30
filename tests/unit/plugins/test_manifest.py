"""Unit tests for PluginManifestParser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from backend.infrastructure.plugins.errors import PluginManifestError
from backend.infrastructure.plugins.manifest import PluginManifestParser
from backend.infrastructure.plugins.types import PluginType


class TestPluginManifestParser:
    """Test the PluginManifestParser class."""

    def setup_method(self) -> None:
        self.parser = PluginManifestParser()

    def test_parse_valid_manifest(self) -> None:
        data = {
            "id": "test-plugin",
            "name": "Test Plugin",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "test_plugin:TestPlugin",
            "author": "Test Author",
            "description": "A test plugin",
            "capabilities": ["transcription"],
        }
        manifest = self.parser.parse_from_dict(data)
        assert manifest.id == "test-plugin"
        assert manifest.name == "Test Plugin"
        assert manifest.version == "1.0.0"
        assert manifest.plugin_type == PluginType.STT
        assert manifest.entry_point == "test_plugin:TestPlugin"

    def test_parse_full_manifest(self) -> None:
        data = {
            "id": "full-plugin",
            "name": "Full Plugin",
            "version": "2.1.0",
            "min_app_version": "1.5.0",
            "max_app_version": "3.0.0",
            "plugin_type": "llm",
            "entry_point": "full_plugin:FullPlugin",
            "author": "Author Name",
            "description": "A full featured plugin",
            "capabilities": ["chat", "completion"],
            "permissions": ["network", "gpu"],
            "models": [{"id": "gpt-4", "size_mb": 1000, "vram_mb": 8000}],
            "dependencies": {"base-plugin": ">=1.0.0"},
            "optional_dependencies": {"extra-plugin": "^2.0.0"},
            "config_schema": {"api_key": {"type": "string", "required": True}},
            "checksum": "abc123",
            "signature": "sig456",
            "homepage": "https://example.com",
            "license": "MIT",
            "tags": ["ai", "llm"],
        }
        manifest = self.parser.parse_from_dict(data)
        assert manifest.id == "full-plugin"
        assert manifest.max_app_version == "3.0.0"
        assert manifest.plugin_type == PluginType.LLM
        assert manifest.checksum == "abc123"
        assert manifest.signature == "sig456"
        assert len(manifest.models) == 1
        assert manifest.models[0].id == "gpt-4"
        assert len(manifest.dependencies) == 1
        assert manifest.dependencies[0].package == "base-plugin"
        assert manifest.dependencies[0].version_spec == ">=1.0.0"

    def test_missing_required_fields(self) -> None:
        data = {"name": "No ID plugin"}
        with pytest.raises(PluginManifestError, match="Missing required manifest"):
            self.parser.parse_from_dict(data)

    def test_invalid_plugin_type(self) -> None:
        data = {
            "id": "bad-type",
            "name": "Bad Type",
            "version": "1.0.0",
            "plugin_type": "unknown_type",
            "entry_point": "mod:Class",
        }
        with pytest.raises(PluginManifestError, match="Unknown plugin type"):
            self.parser.parse_from_dict(data)

    def test_invalid_entry_point_format(self) -> None:
        data = {
            "id": "bad-entry",
            "name": "Bad Entry",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "module_only",
        }
        with pytest.raises(PluginManifestError, match="module:ClassName"):
            self.parser.parse_from_dict(data)

    def test_invalid_version(self) -> None:
        data = {
            "id": "bad-ver",
            "name": "Bad Version",
            "version": "invalid",
            "plugin_type": "stt",
            "entry_point": "mod:Class",
        }
        with pytest.raises(PluginManifestError, match="Invalid version"):
            self.parser.parse_from_dict(data)

    def test_empty_id(self) -> None:
        data = {
            "id": "",
            "name": "Empty ID",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "mod:Class",
        }
        with pytest.raises(PluginManifestError, match="non-empty string"):
            self.parser.parse_from_dict(data)

    def test_permissions_parsing(self) -> None:
        data = {
            "id": "perm-plugin",
            "name": "Perm Plugin",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "mod:Class",
            "permissions": ["network", "gpu", "model_access", "invalid_perm"],
        }
        manifest = self.parser.parse_from_dict(data)
        assert len(manifest.permissions) == 3
        perm_values = [p.value for p in manifest.permissions]
        assert "network" in perm_values
        assert "gpu" in perm_values
        assert "model_access" in perm_values
        assert "invalid_perm" not in perm_values

    def test_warnings_on_incomplete_manifest(self) -> None:
        data = {
            "id": "warn-plugin",
            "name": "Warn Plugin",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "mod:Class",
        }
        manifest = self.parser.parse_from_dict(data)
        warnings = self.parser.validate_manifest(manifest)
        assert len(warnings) > 0
        assert any("no description" in w for w in warnings)
        assert any("no capabilities" in w for w in warnings)

    def test_parse_from_file(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "manifest.json"
        data = {
            "id": "file-plugin",
            "name": "File Plugin",
            "version": "1.0.0",
            "plugin_type": "vision",
            "entry_point": "file_plugin:FilePlugin",
        }
        manifest_path.write_text(json.dumps(data), encoding="utf-8")
        manifest = self.parser.parse_from_file(manifest_path)
        assert manifest.id == "file-plugin"

    def test_parse_from_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            self.parser.parse_from_file("/nonexistent/manifest.json")

    def test_parse_from_file_invalid_json(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "bad.json"
        manifest_path.write_text("{invalid json}", encoding="utf-8")
        with pytest.raises(PluginManifestError, match="Invalid JSON"):
            self.parser.parse_from_file(manifest_path)

    def test_parse_dependencies_format(self) -> None:
        data = {
            "id": "dep-plugin",
            "name": "Dep Plugin",
            "version": "1.0.0",
            "plugin_type": "llm",
            "entry_point": "mod:Class",
            "dependencies": {"pkg-a": ">=1.0.0", "pkg-b": "^2.0.0"},
        }
        manifest = self.parser.parse_from_dict(data)
        assert len(manifest.dependencies) == 2
        deps = {d.package: d.version_spec for d in manifest.dependencies}
        assert deps["pkg-a"] == ">=1.0.0"
        assert deps["pkg-b"] == "^2.0.0"

    def test_min_app_version_default(self) -> None:
        data = {
            "id": "default-min",
            "name": "Default Min",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "mod:Class",
        }
        manifest = self.parser.parse_from_dict(data)
        assert manifest.min_app_version == "1.0.0"
