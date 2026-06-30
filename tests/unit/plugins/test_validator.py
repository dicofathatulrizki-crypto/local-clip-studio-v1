"""Unit tests for PluginValidator."""

from __future__ import annotations

from backend.infrastructure.plugins.types import (
    DependencyGraph,
    PluginDependency,
    PluginManifest,
    PluginType,
)
from backend.infrastructure.plugins.validator import PluginValidator


class TestPluginValidator:
    """Test the PluginValidator class."""

    def setup_method(self) -> None:
        self.validator = PluginValidator()

    def test_validate_valid_manifest(self) -> None:
        manifest = PluginManifest(
            id="valid",
            name="Valid",
            version="1.0.0",
            plugin_type=PluginType.STT,
            entry_point="mod:Class",
            capabilities=["transcription"],
        )
        errors = self.validator.validate_manifest(manifest)
        assert errors == []

    def test_validate_missing_capabilities(self) -> None:
        manifest = PluginManifest(
            id="nocap",
            name="No Capabilities",
            version="1.0.0",
            plugin_type=PluginType.STT,
            entry_point="mod:Class",
            capabilities=[],
        )
        errors = self.validator.validate_manifest(manifest)
        assert any("capabilities" in e for e in errors)

    def test_validate_bad_entry_point(self) -> None:
        manifest = PluginManifest(
            id="bad-ep",
            name="Bad EP",
            version="1.0.0",
            plugin_type=PluginType.STT,
            entry_point="module_only",
            capabilities=["x"],
        )
        errors = self.validator.validate_manifest(manifest)
        assert any("module:ClassName" in e for e in errors)

    def test_validate_unknown_type(self) -> None:
        manifest = PluginManifest(
            id="unknown",
            name="Unknown",
            version="1.0.0",
            plugin_type=PluginType.UNKNOWN,
            entry_point="mod:Class",
            capabilities=["x"],
        )
        errors = self.validator.validate_manifest(manifest)
        assert any("unknown" in e.lower() for e in errors)

    def test_validate_invalid_version(self) -> None:
        manifest = PluginManifest(
            id="bad-ver",
            name="Bad Ver",
            version="not-semver",
            plugin_type=PluginType.STT,
            entry_point="mod:Class",
            capabilities=["x"],
        )
        errors = self.validator.validate_manifest(manifest)
        assert any("semver" in e for e in errors)

    def test_validate_interface_pass(self) -> None:
        manifest = PluginManifest(
            id="test-stt",
            plugin_type=PluginType.STT,
        )
        class MockSTT:
            def load(self): pass
            def transcribe(self): pass
            def get_available_models(self): pass
            def unload(self): pass
            def health_check(self): pass

        missing = self.validator.validate_interface(manifest, MockSTT())
        assert missing == []

    def test_validate_interface_missing_methods(self) -> None:
        manifest = PluginManifest(
            id="bad-stt",
            plugin_type=PluginType.STT,
        )
        class IncompleteSTT:
            pass

        missing = self.validator.validate_interface(manifest, IncompleteSTT())
        assert len(missing) == 5

    def test_validate_interface_non_callable(self) -> None:
        manifest = PluginManifest(
            id="noncall-stt",
            plugin_type=PluginType.STT,
        )
        class NonCallableSTT:
            load = "not_callable"
            transcribe = None
            get_available_models = 42
            unload = []
            health_check = {}

        missing = self.validator.validate_interface(manifest, NonCallableSTT())
        assert len(missing) == 5
        assert any("(not callable)" in m for m in missing)

    def test_validate_version_compatibility_pass(self) -> None:
        manifest = PluginManifest(
            id="compat",
            min_app_version="1.0.0",
            max_app_version="3.0.0",
        )
        errors = self.validator.validate_version_compatibility(manifest, "2.0.0")
        assert errors == []

    def test_validate_version_below_minimum(self) -> None:
        manifest = PluginManifest(
            id="too-old",
            min_app_version="2.0.0",
        )
        errors = self.validator.validate_version_compatibility(manifest, "1.0.0")
        assert len(errors) > 0

    def test_validate_version_above_maximum(self) -> None:
        manifest = PluginManifest(
            id="too-new",
            min_app_version="1.0.0",
            max_app_version="2.0.0",
        )
        errors = self.validator.validate_version_compatibility(manifest, "3.0.0")
        assert len(errors) > 0

    def test_validate_dependencies_missing(self) -> None:
        manifest = PluginManifest(
            id="test-dep",
            name="Test Dep",
            dependencies=[PluginDependency(package="missing-dep", version_spec=">=1.0.0")],
        )
        errors = self.validator.validate_dependencies(manifest, {})
        assert any("not installed" in e for e in errors)

    def test_validate_dependencies_satisfied(self) -> None:
        manifest = PluginManifest(
            id="test-dep",
            name="Test Dep",
            dependencies=[PluginDependency(package="base-plugin", version_spec=">=1.0.0")],
        )
        available = {
            "base-plugin": PluginManifest(id="base-plugin", version="2.0.0"),
        }
        errors = self.validator.validate_dependencies(manifest, available)
        assert errors == []

    def test_detect_cyclic_dependencies(self) -> None:
        manifests = {
            "a": PluginManifest(
                id="a",
                dependencies=[PluginDependency(package="b")],
            ),
            "b": PluginManifest(
                id="b",
                dependencies=[PluginDependency(package="c")],
            ),
            "c": PluginManifest(
                id="c",
                dependencies=[PluginDependency(package="a")],
            ),
        }
        cycles = self.validator.detect_cyclic_dependencies("a", manifests["a"], manifests)
        assert len(cycles) > 0

    def test_no_cyclic_dependencies(self) -> None:
        manifests = {
            "a": PluginManifest(
                id="a",
                dependencies=[PluginDependency(package="b")],
            ),
            "b": PluginManifest(
                id="b",
                dependencies=[PluginDependency(package="c")],
            ),
            "c": PluginManifest(id="c"),
        }
        cycles = self.validator.detect_cyclic_dependencies("a", manifests["a"], manifests)
        assert cycles == []

    def test_detect_duplicates(self) -> None:
        manifests = [
            PluginManifest(id="a", version="1.0.0"),
            PluginManifest(id="b", version="1.0.0"),
            PluginManifest(id="a", version="2.0.0"),
        ]
        duplicates = self.validator.detect_duplicates(manifests)
        assert len(duplicates) == 1
        assert duplicates[0][0] == "a"

    def test_no_duplicates(self) -> None:
        manifests = [
            PluginManifest(id="a", version="1.0.0"),
            PluginManifest(id="b", version="1.0.0"),
        ]
        duplicates = self.validator.detect_duplicates(manifests)
        assert duplicates == []

    def test_build_dependency_graph(self) -> None:
        manifests = [
            PluginManifest(id="a", dependencies=[PluginDependency(package="b")]),
            PluginManifest(id="b"),
        ]
        graph = self.validator.build_dependency_graph(manifests)
        assert "a" in graph.nodes
        assert "b" in graph.nodes["a"]
        assert "a" in graph.edges["b"]

    def test_check_capability(self) -> None:
        manifest = PluginManifest(id="test", capabilities=["transcription", "diarization"])
        assert self.validator.check_capability(manifest, "transcription") is True
        assert self.validator.check_capability(manifest, "translation") is False

    def test_checksum_validation_no_checksum(self) -> None:
        manifest = PluginManifest(id="test", checksum="")
        errors = self.validator.validate_checksum(manifest, [])
        assert errors == []

    def test_checksum_validation_missing_file(self) -> None:
        manifest = PluginManifest(id="test", checksum="abc123")
        errors = self.validator.validate_checksum(manifest, ["/nonexistent/file.py"])
        assert len(errors) > 0

    def test_provider_interface_mapping(self) -> None:
        assert PluginValidator.PROVIDER_INTERFACES[PluginType.STT] == "STTProvider"
        assert PluginValidator.PROVIDER_INTERFACES[PluginType.LLM] == "LLMProvider"
        assert PluginValidator.PROVIDER_INTERFACES[PluginType.VISION] == "VisionProvider"
        assert PluginValidator.PROVIDER_INTERFACES[PluginType.CAPTION] == "CaptionProvider"
        assert PluginValidator.PROVIDER_INTERFACES[PluginType.TRANSLATION] == "TranslationProvider"
        assert PluginValidator.PROVIDER_INTERFACES[PluginType.EXPORT] == "ExportProvider"

    def test_dependency_version_mismatch(self) -> None:
        manifest = PluginManifest(
            id="test-dep",
            dependencies=[PluginDependency(package="base", version_spec=">=2.0.0")],
        )
        available = {
            "base": PluginManifest(id="base", version="1.0.0"),
        }
        errors = self.validator.validate_dependencies(manifest, available)
        assert any("does not satisfy" in e for e in errors)
