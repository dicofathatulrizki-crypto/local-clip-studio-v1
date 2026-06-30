"""Unit tests for PluginSandbox."""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.infrastructure.plugins.errors import PluginPermissionError
from backend.infrastructure.plugins.sandbox import PluginSandbox
from backend.infrastructure.plugins.types import Permission, PluginManifest


class TestPluginSandbox:
    """Test the PluginSandbox class."""

    def setup_method(self) -> None:
        self.sandbox = PluginSandbox()
        self.manifest = PluginManifest(
            id="test-plugin",
            permissions=[Permission.GPU, Permission.NETWORK, Permission.NETWORK_LOCALHOST,
                         Permission.MODEL_ACCESS, Permission.FILESYSTEM_READ],
        )

    def test_grant_and_check_permission(self) -> None:
        self.sandbox.grant_permissions("test-plugin", [
            Permission.GPU, Permission.NETWORK,
        ])
        assert self.sandbox.check_permission(self.manifest, Permission.GPU) is True
        assert self.sandbox.check_permission(self.manifest, Permission.NETWORK) is True

    def test_check_undeclared_permission(self) -> None:
        self.sandbox.grant_permissions("test-plugin", [Permission.GPU])
        # Permission not declared in manifest
        manifest = PluginManifest(id="no-perms")
        with pytest.raises(PluginPermissionError, match="not declared"):
            self.sandbox.check_permission(manifest, Permission.GPU)

    def test_check_not_granted_permission(self) -> None:
        self.sandbox.grant_permissions("test-plugin", [Permission.GPU])
        with pytest.raises(PluginPermissionError, match="not granted"):
            self.sandbox.check_permission(self.manifest, Permission.MODEL_ACCESS)

    def test_revoke_permissions(self) -> None:
        self.sandbox.grant_permissions("test-plugin", [Permission.GPU])
        self.sandbox.revoke_permissions("test-plugin")
        with pytest.raises(PluginPermissionError):
            self.sandbox.check_permission(self.manifest, Permission.GPU)

    def test_granted_permissions_list(self) -> None:
        self.sandbox.grant_permissions("test-plugin", [Permission.GPU, Permission.NETWORK])
        granted = self.sandbox.get_granted_permissions("test-plugin")
        assert Permission.GPU in granted
        assert Permission.NETWORK in granted
        assert Permission.MODEL_ACCESS not in granted

    def test_granted_permissions_unknown_plugin(self) -> None:
        granted = self.sandbox.get_granted_permissions("unknown")
        assert granted == []

    def test_resolve_path_allowed(self, tmp_path: Path) -> None:
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        self.sandbox.set_allowed_directories([str(allowed_dir)])
        resolved = self.sandbox.resolve_path(self.manifest, str(allowed_dir / "file.txt"))
        assert str(resolved) == str((allowed_dir / "file.txt").resolve())

    def test_resolve_path_denied(self, tmp_path: Path) -> None:
        allowed_dir = tmp_path / "allowed"
        denied_dir = tmp_path / "denied"
        allowed_dir.mkdir()
        denied_dir.mkdir()
        self.sandbox.set_allowed_directories([str(allowed_dir)])
        with pytest.raises(PluginPermissionError, match="outside allowed directories"):
            self.sandbox.resolve_path(self.manifest, str(denied_dir / "file.txt"))

    def test_resolve_path_traversal_attempt(self, tmp_path: Path) -> None:
        self.sandbox.set_allowed_directories([str(tmp_path)])
        with pytest.raises(PluginPermissionError, match="Path traversal"):
            self.sandbox.resolve_path(self.manifest, "../etc/passwd")

    def test_resolve_path_no_allowed_dirs(self, tmp_path: Path) -> None:
        resolved = self.sandbox.resolve_path(self.manifest, str(tmp_path / "file.txt"))
        assert resolved == (tmp_path / "file.txt").resolve()

    def test_validate_network_full(self) -> None:
        self.sandbox.grant_permissions("test-plugin", [Permission.NETWORK])
        assert self.sandbox.validate_network_access(self.manifest, "https://api.example.com") is True

    def test_validate_network_localhost_allowed(self) -> None:
        self.sandbox.grant_permissions("test-plugin", [Permission.NETWORK_LOCALHOST])
        assert self.sandbox.validate_network_access(self.manifest, "http://localhost:8080") is True
        assert self.sandbox.validate_network_access(self.manifest, "http://127.0.0.1:5000") is True

    def test_validate_network_localhost_denied_external(self) -> None:
        self.sandbox.grant_permissions("test-plugin", [Permission.NETWORK_LOCALHOST])
        with pytest.raises(PluginPermissionError, match="not localhost"):
            self.sandbox.validate_network_access(self.manifest, "https://api.example.com")

    def test_validate_network_no_permission(self) -> None:
        manifest = PluginManifest(id="no-net", permissions=[Permission.GPU])
        self.sandbox.grant_permissions("no-net", [Permission.GPU])
        with pytest.raises(PluginPermissionError, match="did not declare network"):
            self.sandbox.validate_network_access(manifest, "https://api.example.com")

    def test_validate_model_access(self) -> None:
        manifest = PluginManifest(
            id="model-plugin",
            permissions=[Permission.MODEL_ACCESS],
            models=[{"id": "whisper-large", "size_mb": 3000}],
        )
        self.sandbox.grant_permissions("model-plugin", [Permission.MODEL_ACCESS])
        assert self.sandbox.validate_model_access(manifest, "whisper-large") is True

    def test_validate_model_access_not_declared(self) -> None:
        manifest = PluginManifest(
            id="model-plugin",
            permissions=[Permission.MODEL_ACCESS],
            models=[{"id": "whisper-large"}],
        )
        self.sandbox.grant_permissions("model-plugin", [Permission.MODEL_ACCESS])
        with pytest.raises(PluginPermissionError, match="not declared"):
            self.sandbox.validate_model_access(manifest, "unknown-model")

    def test_validate_config_missing_required(self) -> None:
        manifest = PluginManifest(
            id="config-plugin",
            config_schema={"api_key": {"type": "string", "required": True}},
        )
        errors = self.sandbox.validate_config(manifest, {})
        assert any("Missing required config" in e for e in errors)

    def test_validate_config_type_mismatch(self) -> None:
        manifest = PluginManifest(
            id="config-plugin",
            config_schema={
                "timeout": {"type": "integer"},
                "enabled": {"type": "boolean"},
                "name": {"type": "string"},
            },
        )
        errors = self.sandbox.validate_config(manifest, {
            "timeout": "not_an_int",
            "enabled": "not_a_bool",
            "name": "valid_name",
        })
        assert any("should be an integer" in e for e in errors)
        assert any("should be a boolean" in e for e in errors)
        assert not any("should be a string" in e for e in errors)

    def test_validate_config_enum(self) -> None:
        manifest = PluginManifest(
            id="config-plugin",
            config_schema={
                "quality": {"type": "string", "enum": ["low", "medium", "high"]},
            },
        )
        errors = self.sandbox.validate_config(manifest, {"quality": "ultra"})
        assert any("not in allowed values" in e for e in errors)

    def test_validate_config_empty_schema(self) -> None:
        errors = self.sandbox.validate_config(self.manifest, {"key": "value"})
        assert errors == []

    def test_set_allowed_directories(self, tmp_path: Path) -> None:
        d1 = tmp_path / "dir1"
        d2 = tmp_path / "dir2"
        d1.mkdir()
        d2.mkdir()
        self.sandbox.set_allowed_directories([str(d1), str(d2)])
        resolved = self.sandbox.resolve_path(self.manifest, str(d1 / "f.txt"))
        assert resolved == (d1 / "f.txt").resolve()
