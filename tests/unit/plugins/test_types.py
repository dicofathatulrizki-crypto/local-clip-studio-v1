"""Unit tests for plugin types (types.py)."""

from __future__ import annotations

from backend.infrastructure.plugins.types import (
    DependencyGraph,
    Permission,
    PluginDependency,
    PluginInfo,
    PluginInstance,
    PluginManifest,
    PluginModelInfo,
    PluginRegistration,
    PluginState,
    PluginType,
)


class TestPluginState:
    """Test PluginState enum values."""

    def test_state_values(self) -> None:
        assert PluginState.DISCOVERED.value == "discovered"
        assert PluginState.LOADED.value == "loaded"
        assert PluginState.INITIALIZED.value == "initialized"
        assert PluginState.ACTIVE.value == "active"
        assert PluginState.ERROR.value == "error"
        assert PluginState.SHUTDOWN.value == "shutdown"
        assert PluginState.DISABLED.value == "disabled"

    def test_state_transitions(self) -> None:
        valid_active = {PluginState.ACTIVE, PluginState.INITIALIZED, PluginState.LOADED}
        assert PluginState.ACTIVE in valid_active
        assert PluginState.INITIALIZED in valid_active
        assert PluginState.LOADED in valid_active
        assert PluginState.DISCOVERED not in valid_active


class TestPluginType:
    """Test PluginType enum values."""

    def test_type_values(self) -> None:
        assert PluginType.STT.value == "stt"
        assert PluginType.LLM.value == "llm"
        assert PluginType.VISION.value == "vision"
        assert PluginType.CAPTION.value == "caption"
        assert PluginType.TRANSLATION.value == "translation"
        assert PluginType.EXPORT.value == "export"
        assert PluginType.UNKNOWN.value == "unknown"

    def test_valid_types(self) -> None:
        valid = {PluginType.STT, PluginType.LLM, PluginType.VISION,
                 PluginType.CAPTION, PluginType.TRANSLATION, PluginType.EXPORT}
        assert PluginType.STT in valid
        assert PluginType.UNKNOWN not in valid


class TestPermission:
    """Test Permission enum values."""

    def test_permission_values(self) -> None:
        assert Permission.GPU.value == "gpu"
        assert Permission.NETWORK.value == "network"
        assert Permission.NETWORK_LOCALHOST.value == "network:localhost"
        assert Permission.FILESYSTEM_READ.value == "filesystem:read"
        assert Permission.FILESYSTEM_WRITE.value == "filesystem:write"
        assert Permission.MODEL_ACCESS.value == "model_access"


class TestPluginManifest:
    """Test PluginManifest dataclass."""

    def test_default_manifest(self) -> None:
        manifest = PluginManifest()
        assert manifest.id == ""
        assert manifest.version == "0.0.0"
        assert manifest.plugin_type == PluginType.UNKNOWN
        assert manifest.capabilities == []
        assert manifest.permissions == []
        assert manifest.dependencies == []

    def test_manifest_with_values(self) -> None:
        manifest = PluginManifest(
            id="test-plugin",
            name="Test Plugin",
            version="1.0.0",
            plugin_type=PluginType.STT,
            capabilities=["transcription", "diarization"],
        )
        assert manifest.id == "test-plugin"
        assert manifest.name == "Test Plugin"
        assert manifest.version == "1.0.0"
        assert manifest.plugin_type == PluginType.STT
        assert "transcription" in manifest.capabilities

    def test_manifest_compatibility(self) -> None:
        manifest = PluginManifest(
            id="compat-plugin",
            min_app_version="1.0.0",
            max_app_version="2.0.0",
        )
        assert manifest.is_compatible_with_app("1.5.0") is True
        assert manifest.is_compatible_with_app("0.9.0") is False
        assert manifest.is_compatible_with_app("2.0.0") is True
        assert manifest.is_compatible_with_app("2.1.0") is False

    def test_manifest_no_max_version(self) -> None:
        manifest = PluginManifest(
            id="unlimited-plugin",
            min_app_version="1.0.0",
            max_app_version=None,
        )
        assert manifest.is_compatible_with_app("1.0.0") is True
        assert manifest.is_compatible_with_app("10.0.0") is True
        assert manifest.is_compatible_with_app("0.5.0") is False


class TestPluginInstance:
    """Test PluginInstance dataclass."""

    def test_default_instance(self) -> None:
        instance = PluginInstance()
        assert instance.state == PluginState.DISCOVERED
        assert instance.enabled is True
        assert instance.priority == 100
        assert instance.instance is None
        assert instance.ref_count == 0

    def test_instance_with_manifest(self) -> None:
        manifest = PluginManifest(id="my-plugin", name="My Plugin")
        instance = PluginInstance(
            manifest=manifest,
            state=PluginState.LOADED,
            priority=50,
        )
        assert instance.manifest.id == "my-plugin"
        assert instance.state == PluginState.LOADED
        assert instance.priority == 50

    def test_instance_state_transition(self) -> None:
        instance = PluginInstance()
        instance.state = PluginState.LOADED
        assert instance.state == PluginState.LOADED
        instance.state = PluginState.ACTIVE
        assert instance.state == PluginState.ACTIVE


class TestPluginInfo:
    """Test PluginInfo dataclass."""

    def test_info_from_manifest(self) -> None:
        manifest = PluginManifest(
            id="info-plugin",
            name="Info Plugin",
            version="2.0.0",
            plugin_type=PluginType.LLM,
            capabilities=["generation"],
            config_schema={"key": {"type": "string"}},
        )
        info = PluginInfo(
            id=manifest.id,
            name=manifest.name,
            version=manifest.version,
            plugin_type=manifest.plugin_type.value,
            capabilities=list(manifest.capabilities),
            config_schema=dict(manifest.config_schema),
        )
        assert info.id == "info-plugin"
        assert info.name == "Info Plugin"
        assert info.plugin_type == "llm"
        assert info.state == "discovered"


class TestPluginDependency:
    """Test PluginDependency dataclass."""

    def test_dependency_defaults(self) -> None:
        dep = PluginDependency()
        assert dep.package == ""
        assert dep.version_spec == ""

    def test_dependency_with_values(self) -> None:
        dep = PluginDependency(package="whisper", version_spec=">=1.0.0")
        assert dep.package == "whisper"
        assert dep.version_spec == ">=1.0.0"


class TestPluginModelInfo:
    """Test PluginModelInfo dataclass."""

    def test_model_defaults(self) -> None:
        model = PluginModelInfo()
        assert model.id == ""
        assert model.size_mb == 0

    def test_model_with_values(self) -> None:
        model = PluginModelInfo(id="whisper-large", size_mb=3000, vram_mb=6000)
        assert model.id == "whisper-large"
        assert model.size_mb == 3000
        assert model.vram_mb == 6000


class TestPluginRegistration:
    """Test PluginRegistration dataclass."""

    def test_registration_defaults(self) -> None:
        reg = PluginRegistration()
        assert reg.instance.state == PluginState.DISCOVERED
        assert reg.registered_at == 0.0

    def test_registration_with_instance(self) -> None:
        instance = PluginInstance()
        reg = PluginRegistration(instance=instance, registered_at=100.0)
        assert reg.instance is instance
        assert reg.registered_at == 100.0


class TestDependencyGraph:
    """Test DependencyGraph dataclass."""

    def test_empty_graph(self) -> None:
        graph = DependencyGraph()
        assert graph.nodes == {}
        assert graph.edges == {}

    def test_graph_with_nodes(self) -> None:
        graph = DependencyGraph(
            nodes={"a": {"b"}, "b": set()},
            edges={"b": {"a"}},
        )
        assert "a" in graph.nodes
        assert "b" in graph.nodes["a"]
        assert "a" in graph.edges["b"]
