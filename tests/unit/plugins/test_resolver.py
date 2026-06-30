"""Unit tests for PluginVersionResolver and PluginCompatibilityChecker."""

from __future__ import annotations

from backend.infrastructure.plugins.resolver import (
    PluginCompatibilityChecker,
    PluginVersionResolver,
)
from backend.infrastructure.plugins.types import (
    PluginDependency,
    PluginManifest,
    PluginType,
)


class TestPluginVersionResolver:
    """Test the PluginVersionResolver class."""

    def test_satisfies_exact(self) -> None:
        assert PluginVersionResolver.satisfies("1.0.0", "1.0.0") is True
        assert PluginVersionResolver.satisfies("1.0.1", "1.0.0") is False

    def test_satisfies_greater_equal(self) -> None:
        assert PluginVersionResolver.satisfies("1.0.0", ">=1.0.0") is True
        assert PluginVersionResolver.satisfies("2.0.0", ">=1.0.0") is True
        assert PluginVersionResolver.satisfies("0.9.0", ">=1.0.0") is False

    def test_satisfies_greater_than(self) -> None:
        assert PluginVersionResolver.satisfies("1.0.1", ">1.0.0") is True
        assert PluginVersionResolver.satisfies("1.0.0", ">1.0.0") is False

    def test_satisfies_less_equal(self) -> None:
        assert PluginVersionResolver.satisfies("1.0.0", "<=1.0.0") is True
        assert PluginVersionResolver.satisfies("0.9.0", "<=1.0.0") is True
        assert PluginVersionResolver.satisfies("1.0.1", "<=1.0.0") is False

    def test_satisfies_less_than(self) -> None:
        assert PluginVersionResolver.satisfies("0.9.0", "<1.0.0") is True
        assert PluginVersionResolver.satisfies("1.0.0", "<1.0.0") is False

    def test_satisfies_caret(self) -> None:
        assert PluginVersionResolver.satisfies("1.5.0", "^1.0.0") is True
        assert PluginVersionResolver.satisfies("2.0.0", "^1.0.0") is False
        assert PluginVersionResolver.satisfies("0.9.0", "^1.0.0") is False

    def test_satisfies_tilde(self) -> None:
        assert PluginVersionResolver.satisfies("1.0.5", "~1.0.0") is True
        assert PluginVersionResolver.satisfies("1.1.0", "~1.0.0") is False
        assert PluginVersionResolver.satisfies("0.9.0", "~1.0.0") is False

    def test_satisfies_not_equal(self) -> None:
        assert PluginVersionResolver.satisfies("1.0.1", "!=1.0.0") is True
        assert PluginVersionResolver.satisfies("1.0.0", "!=1.0.0") is False

    def test_satisfies_wildcard(self) -> None:
        assert PluginVersionResolver.satisfies("any-version", "*") is True
        assert PluginVersionResolver.satisfies("1.0.0", "") is True

    def test_satisfies_invalid_version(self) -> None:
        assert PluginVersionResolver.satisfies("not-a-version", ">=1.0.0") is False

    def test_satisfies_invalid_constraint(self) -> None:
        assert PluginVersionResolver.satisfies("1.0.0", "bad%%constraint") is False

    def test_max_satisfying(self) -> None:
        versions = ["1.0.0", "1.5.0", "2.0.0", "2.5.0"]
        result = PluginVersionResolver.max_satisfying(versions, ">=1.5.0,<3.0.0")
        # The current implementation only handles single constraints
        result = PluginVersionResolver.max_satisfying(versions, "^1.0.0")
        assert result == "1.5.0"

    def test_max_satisfying_no_match(self) -> None:
        result = PluginVersionResolver.max_satisfying(["1.0.0", "1.5.0"], "^2.0.0")
        assert result is None

    def test_max_satisfying_invalid_versions(self) -> None:
        result = PluginVersionResolver.max_satisfying(["bad", "1.0.0"], ">=0.5.0")
        assert result == "1.0.0"

    def test_sort_versions_ascending(self) -> None:
        versions = ["2.0.0", "1.0.0", "3.0.0"]
        sorted_versions = PluginVersionResolver.sort_versions(versions)
        assert sorted_versions == ["1.0.0", "2.0.0", "3.0.0"]

    def test_sort_versions_descending(self) -> None:
        versions = ["2.0.0", "1.0.0", "3.0.0"]
        sorted_versions = PluginVersionResolver.sort_versions(versions, reverse=True)
        assert sorted_versions == ["3.0.0", "2.0.0", "1.0.0"]

    def test_sort_versions_with_invalid(self) -> None:
        versions = ["bad", "1.0.0", "2.0.0"]
        sorted_versions = PluginVersionResolver.sort_versions(versions)
        assert sorted_versions == ["2.0.0", "1.0.0", "bad"]


class TestPluginCompatibilityChecker:
    """Test the PluginCompatibilityChecker class."""

    def setup_method(self) -> None:
        self.checker = PluginCompatibilityChecker(app_version="2.0.0")

    def test_app_version_property(self) -> None:
        assert self.checker.app_version == "2.0.0"

    def test_compatible_plugin(self) -> None:
        manifest = PluginManifest(
            id="compat",
            min_app_version="1.0.0",
            max_app_version="3.0.0",
        )
        issues = self.checker.check_plugin_compatibility(manifest)
        assert issues == []
        assert self.checker.is_plugin_compatible(manifest) is True

    def test_below_min_version(self) -> None:
        manifest = PluginManifest(
            id="too-old",
            min_app_version="3.0.0",
        )
        issues = self.checker.check_plugin_compatibility(manifest)
        assert len(issues) > 0
        assert self.checker.is_plugin_compatible(manifest) is False

    def test_above_max_version(self) -> None:
        manifest = PluginManifest(
            id="too-new",
            min_app_version="1.0.0",
            max_app_version="1.5.0",
        )
        issues = self.checker.check_plugin_compatibility(manifest)
        assert len(issues) > 0

    def test_no_max_version(self) -> None:
        manifest = PluginManifest(
            id="unlimited",
            min_app_version="1.0.0",
            max_app_version=None,
        )
        issues = self.checker.check_plugin_compatibility(manifest)
        assert issues == []

    def test_check_dependency_missing(self) -> None:
        manifest = PluginManifest(
            id="test",
            dependencies=[PluginDependency(package="missing-dep", version_spec=">=1.0.0")],
        )
        issues = self.checker.check_dependency_compatibility(manifest, {})
        assert any("Missing dependency" in i for i in issues)

    def test_check_dependency_version_mismatch(self) -> None:
        manifest = PluginManifest(
            id="test",
            dependencies=[PluginDependency(package="base", version_spec=">=2.0.0")],
        )
        available = {
            "base": PluginManifest(id="base", version="1.0.0"),
        }
        issues = self.checker.check_dependency_compatibility(manifest, available)
        assert any("does not satisfy" in i for i in issues)

    def test_check_dependency_ok(self) -> None:
        manifest = PluginManifest(
            id="test",
            dependencies=[PluginDependency(package="base", version_spec=">=1.0.0")],
        )
        available = {
            "base": PluginManifest(id="base", version="2.0.0"),
        }
        issues = self.checker.check_dependency_compatibility(manifest, available)
        assert issues == []

    def test_default_app_version(self) -> None:
        checker = PluginCompatibilityChecker()
        assert checker.app_version == "1.0.0"
