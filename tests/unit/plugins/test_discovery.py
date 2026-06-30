"""Unit tests for PluginDiscovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from backend.infrastructure.plugins.discovery import PluginDiscovery
from backend.infrastructure.plugins.errors import PluginDuplicateError
from backend.infrastructure.plugins.manifest import PluginManifestParser


class TestPluginDiscovery:
    """Test the PluginDiscovery class."""

    def setup_method(self) -> None:
        self.discovery = PluginDiscovery()

    def test_empty_directories(self) -> None:
        manifests = self.discovery.discover_all()
        assert manifests == []

    def test_discover_single_plugin(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "plugins" / "my-plugin"
        plugin_dir.mkdir(parents=True)
        manifest_data = {
            "id": "my-plugin",
            "name": "My Plugin",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "my_plugin:MyPlugin",
        }
        (plugin_dir / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

        self.discovery.add_search_directory(str(plugin_dir.parent))
        manifests = self.discovery.discover_all()
        assert len(manifests) == 1
        assert manifests[0].id == "my-plugin"

    def test_discover_builtin_plugins(self, tmp_path: Path) -> None:
        builtin_dir = tmp_path / "builtins"
        builtin_dir.mkdir()
        for name in ["stt-plugin", "llm-plugin", "vision-plugin"]:
            plugin_dir = builtin_dir / name
            plugin_dir.mkdir()
            manifest_data = {
                "id": name,
                "name": name.replace("-", " ").title(),
                "version": "1.0.0",
                "plugin_type": name.split("-")[0],
                "entry_point": f"{name.replace('-', '_')}:Plugin",
            }
            (plugin_dir / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

        self.discovery.add_search_directory(str(builtin_dir), is_builtin=True)
        manifests = self.discovery.discover_all()
        assert len(manifests) == 3
        plugin_ids = {m.id for m in manifests}
        assert "stt-plugin" in plugin_ids
        assert "llm-plugin" in plugin_ids
        assert "vision-plugin" in plugin_ids

    def test_discover_external_plugins(self, tmp_path: Path) -> None:
        ext_dir = tmp_path / "external"
        ext_dir.mkdir()
        plugin_dir = ext_dir / "ext-plugin"
        plugin_dir.mkdir()
        manifest_data = {
            "id": "ext-plugin",
            "name": "External Plugin",
            "version": "1.0.0",
            "plugin_type": "llm",
            "entry_point": "ext_plugin:ExtPlugin",
        }
        (plugin_dir / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

        self.discovery.add_search_directory(str(ext_dir))
        manifests = self.discovery.discover_all()
        assert len(manifests) == 1
        assert manifests[0].id == "ext-plugin"

    def test_nonexistent_directory(self) -> None:
        self.discovery.add_search_directory("/nonexistent/path")
        manifests = self.discovery.discover_all()
        assert manifests == []

    def test_duplicate_plugin_detection(self, tmp_path: Path) -> None:
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        for d in [dir1, dir2]:
            pdir = d / "dup-plugin"
            pdir.mkdir()
            manifest_data = {
                "id": "dup-plugin",
                "name": "Dup Plugin",
                "version": "1.0.0",
                "plugin_type": "stt",
                "entry_point": "dup:Plugin",
            }
            (pdir / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

        self.discovery.add_search_directory(str(dir1))
        self.discovery.add_search_directory(str(dir2))
        with pytest.raises(PluginDuplicateError):
            self.discovery.discover_all()

    def test_invalid_manifest_skipped(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "bad-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "manifest.json").write_text("{invalid}", encoding="utf-8")

        self.discovery.add_search_directory(str(plugin_dir.parent))
        manifests = self.discovery.discover_all()
        assert len(manifests) == 0

    def test_missing_manifest_skipped(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "empty-plugin"
        plugin_dir.mkdir()

        self.discovery.add_search_directory(str(plugin_dir.parent))
        manifests = self.discovery.discover_all()
        assert len(manifests) == 0

    def test_search_directories_property(self, tmp_path: Path) -> None:
        assert len(self.discovery.search_directories) == 0
        self.discovery.add_search_directory("/path/a")
        self.discovery.add_search_directory("/path/b")
        assert len(self.discovery.search_directories) == 2

    def test_set_directories_replaces(self, tmp_path: Path) -> None:
        self.discovery.add_search_directory("/old/path")
        self.discovery.set_directories(["/new/a"], ["/new/b"])
        paths = [str(p) for p in self.discovery.search_directories]
        assert "/new/a" in paths
        assert "/new/b" in paths
        assert "/old/path" not in paths

    def test_discover_builtin_and_external(self, tmp_path: Path) -> None:
        builtin_dir = tmp_path / "builtins"
        builtin_dir.mkdir()
        ext_dir = tmp_path / "external"
        ext_dir.mkdir()

        for base, name, ptype in [(builtin_dir, "builtin-stt", "stt"),
                                   (ext_dir, "external-llm", "llm")]:
            pdir = base / name
            pdir.mkdir()
            data = {
                "id": name, "name": name, "version": "1.0.0",
                "plugin_type": ptype, "entry_point": "mod:Class",
            }
            (pdir / "manifest.json").write_text(json.dumps(data), encoding="utf-8")

        self.discovery.set_directories([str(builtin_dir)], [str(ext_dir)])
        all_m = self.discovery.discover_all()
        assert len(all_m) == 2

        builtin_m = self.discovery.discover_builtin()
        assert len(builtin_m) == 1
        assert builtin_m[0].id == "builtin-stt"

        external_m = self.discovery.discover_external()
        assert len(external_m) == 1
        assert external_m[0].id == "external-llm"

    def test_manifest_source_path_in_raw(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "src" / "my-plugin"
        plugin_dir.mkdir(parents=True)
        data = {
            "id": "my-plugin",
            "name": "My Plugin",
            "version": "1.0.0",
            "plugin_type": "stt",
            "entry_point": "mod:Class",
        }
        (plugin_dir / "manifest.json").write_text(json.dumps(data), encoding="utf-8")

        self.discovery.add_search_directory(str(plugin_dir.parent))
        manifests = self.discovery.discover_all()
        assert len(manifests) == 1
        assert manifests[0].raw.get("id") == "my-plugin"
