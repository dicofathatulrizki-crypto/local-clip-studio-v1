"""Unit tests for plugin errors (errors.py)."""

from __future__ import annotations

from backend.infrastructure.plugins.errors import (
    PluginCapabilityError,
    PluginDependencyError,
    PluginDuplicateError,
    PluginError,
    PluginIntegrityError,
    PluginLoadError,
    PluginManifestError,
    PluginNotFoundError,
    PluginPermissionError,
    PluginRuntimeError,
    PluginVersionError,
    translate_plugin_error,
)


class TestPluginError:
    """Test the PluginError base class."""

    def test_base_error(self) -> None:
        error = PluginError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.error_code == "ERR-PLUG-000"
        assert error.plugin_id == ""

    def test_error_with_plugin_id(self) -> None:
        error = PluginError("Error", plugin_id="my-plugin")
        assert error.plugin_id == "my-plugin"

    def test_to_dict(self) -> None:
        error = PluginError("Test error", plugin_id="p1", error_code="ERR-TEST")
        d = error.to_dict()
        assert d["code"] == "ERR-TEST"
        assert d["plugin_id"] == "p1"
        assert d["message"] == "Test error"


class TestPluginLoadError:
    """Test PluginLoadError."""

    def test_load_error(self) -> None:
        error = PluginLoadError("Failed to import module", plugin_id="whisper")
        assert error.error_code == "ERR-PLUG-001"
        assert "import" in str(error).lower()
        assert error.plugin_id == "whisper"
        assert "Check plugin compatibility" in error.recovery_hint


class TestPluginManifestError:
    """Test PluginManifestError."""

    def test_manifest_error(self) -> None:
        error = PluginManifestError("Missing required field: id")
        assert error.error_code == "ERR-PLUG-002"
        assert "Plugin developer" in error.recovery_hint


class TestPluginRuntimeError:
    """Test PluginRuntimeError."""

    def test_runtime_error(self) -> None:
        error = PluginRuntimeError("Plugin crashed")
        assert error.error_code == "ERR-PLUG-003"
        assert "disabled" in error.recovery_hint.lower()


class TestPluginPermissionError:
    """Test PluginPermissionError."""

    def test_permission_error(self) -> None:
        error = PluginPermissionError("Network access denied", plugin_id="net-plugin")
        assert error.error_code == "ERR-PLUG-004"
        assert error.plugin_id == "net-plugin"


class TestPluginNotFoundError:
    """Test PluginNotFoundError."""

    def test_not_found_error(self) -> None:
        error = PluginNotFoundError("missing-plugin")
        assert error.error_code == "ERR-PLUG-005"
        assert "missing-plugin" in str(error)
        assert error.plugin_id == "missing-plugin"


class TestPluginDependencyError:
    """Test PluginDependencyError."""

    def test_dependency_error(self) -> None:
        error = PluginDependencyError(
            "Missing dependency: whisper", plugin_id="my-plugin", dependency="whisper"
        )
        assert error.error_code == "ERR-PLUG-006"
        assert error.dependency == "whisper"
        assert error.plugin_id == "my-plugin"


class TestPluginVersionError:
    """Test PluginVersionError."""

    def test_version_error(self) -> None:
        error = PluginVersionError("Version 2.0.0 not compatible")
        assert error.error_code == "ERR-PLUG-007"
        assert "Update" in error.recovery_hint


class TestPluginDuplicateError:
    """Test PluginDuplicateError."""

    def test_duplicate_error(self) -> None:
        error = PluginDuplicateError("dup-plugin", "/path/to/existing")
        assert "dup-plugin" in str(error)
        assert error.error_code == "ERR-PLUG-008"
        assert error.plugin_id == "dup-plugin"


class TestPluginCapabilityError:
    """Test PluginCapabilityError."""

    def test_capability_error(self) -> None:
        error = PluginCapabilityError("stt-plugin", "diarization")
        assert error.capability == "diarization"
        assert error.plugin_id == "stt-plugin"
        assert "diarization" in str(error)


class TestPluginIntegrityError:
    """Test PluginIntegrityError."""

    def test_integrity_error(self) -> None:
        error = PluginIntegrityError("Checksum mismatch", plugin_id="p1")
        assert error.error_code == "ERR-PLUG-010"
        assert error.plugin_id == "p1"


class TestTranslatePluginError:
    """Test the translate_plugin_error function."""

    def test_translate_plugin_error_passthrough(self) -> None:
        original = PluginLoadError("load failed")
        result = translate_plugin_error(original)
        assert result is original

    def test_translate_import_error(self) -> None:
        result = translate_plugin_error(ImportError("No module named 'xyz'"), "p1")
        assert isinstance(result, PluginLoadError)
        assert "xyz" in str(result)

    def test_translate_module_not_found(self) -> None:
        result = translate_plugin_error(ModuleNotFoundError("No module named 'xyz'"), "p1")
        assert isinstance(result, PluginLoadError)
        assert "xyz" in str(result)

    def test_translate_permission_error(self) -> None:
        result = translate_plugin_error(PermissionError("Access denied"), "p1")
        assert isinstance(result, PluginPermissionError)

    def test_translate_value_error(self) -> None:
        result = translate_plugin_error(ValueError("Bad value"), "p1")
        assert isinstance(result, PluginManifestError)

    def test_translate_generic_error(self) -> None:
        result = translate_plugin_error(RuntimeError("Something broke"), "p1")
        assert isinstance(result, PluginRuntimeError)

    def test_translate_without_plugin_id(self) -> None:
        result = translate_plugin_error(RuntimeError("Boom"))
        assert isinstance(result, PluginRuntimeError)
        assert result.plugin_id == ""
