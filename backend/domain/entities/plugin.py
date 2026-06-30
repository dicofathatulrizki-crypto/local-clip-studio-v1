"""Plugin entity — represents an installed AI plugin.

Each plugin implements one of the provider interfaces (STT, LLM, Vision,
Caption, Translation, Export). Plugins follow a lifecycle:
DISCOVERED → LOADED → INITIALIZED → ACTIVE → ERROR → SHUTDOWN → DISABLED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.domain.exceptions import (
    CyclicDependencyError,
    DuplicatePluginError,
    InvalidTransitionError,
    PluginError,
)
from backend.domain.value_objects import PluginState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Plugin:
    """An installed AI plugin.

    Business rules:
    - Plugin ID must be unique across all installed plugins
    - Entry point must be in format 'module:ClassName'
    - State transitions follow SRS §11.6 plugin lifecycle
    - Dependencies must form an acyclic graph (no circular deps)
    - Version must follow semantic versioning
    """

    # ─── Identity ──────────────────────────────────────────
    id: str = ""
    name: str = ""
    version: str = "0.0.0"

    # ─── Type & Entry Point ────────────────────────────────
    plugin_type: str = "unknown"  # stt, llm, vision, caption, translation, export
    entry_point: str = ""

    # ─── Metadata ──────────────────────────────────────────
    author: str = ""
    description: str = ""
    capabilities: list[str] = field(default_factory=list)

    # ─── Lifecycle ─────────────────────────────────────────
    state: PluginState = PluginState.DISCOVERED
    priority: int = 100
    enabled: bool = True

    # ─── Dependencies ──────────────────────────────────────
    dependencies: list[str] = field(default_factory=list)
    optional_dependencies: list[str] = field(default_factory=list)

    # ─── Permissions ───────────────────────────────────────
    permissions: list[str] = field(default_factory=list)

    # ─── Runtime ───────────────────────────────────────────
    health_status: str = "unknown"
    error_message: str = ""
    loaded_at: float = 0.0
    last_health_check: float = 0.0

    # ─── Timestamps ────────────────────────────────────────
    created_at: datetime = field(default_factory=_utcnow)

    SUPPORTED_TYPES: set[str] = {
        "stt", "llm", "vision", "caption", "translation", "export",
    }

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise PluginError("Plugin ID cannot be empty")
        if self.entry_point and ":" not in self.entry_point:
            raise PluginError(
                f"Entry point must be in 'module:ClassName' format, "
                f"got '{self.entry_point}'"
            )
        if self.plugin_type not in self.SUPPORTED_TYPES:
            raise PluginError(
                f"Unsupported plugin type '{self.plugin_type}'. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_TYPES))}"
            )

    # ─── Lifecycle Transitions ─────────────────────────────

    def _transition_to(self, target: PluginState) -> None:
        if not self.state.can_transition_to(target):
            raise InvalidTransitionError(
                f"Cannot transition plugin from "
                f"'{self.state.value}' to '{target.value}'"
            )
        self.state = target

    def load(self) -> None:
        """Transition from DISCOVERED to LOADED."""
        self._transition_to(PluginState.LOADED)

    def initialize(self) -> None:
        """Transition from LOADED to INITIALIZED."""
        self._transition_to(PluginState.INITIALIZED)

    def activate(self) -> None:
        """Transition from INITIALIZED to ACTIVE."""
        self._transition_to(PluginState.ACTIVE)

    def mark_error(self, message: str = "") -> None:
        """Transition to ERROR state with error message."""
        self._transition_to(PluginState.ERROR)
        self.error_message = message
        self.health_status = "error"

    def shutdown(self) -> None:
        """Transition to SHUTDOWN state."""
        self._transition_to(PluginState.SHUTDOWN)
        self.health_status = "shutdown"

    def disable(self) -> None:
        """Disable the plugin (must be in SHUTDOWN state)."""
        self._transition_to(PluginState.DISABLED)
        self.enabled = False

    # ─── Dependency Validation ─────────────────────────────

    def check_cyclic_dependency(
        self,
        all_plugins: dict[str, Plugin],
        path: list[str] | None = None,
    ) -> None:
        """Check if this plugin creates a cyclic dependency.

        Args:
            all_plugins: Dict of all plugin IDs to their Plugin objects.
            path: Current dependency path (internal recursion).

        Raises:
            CyclicDependencyError: If a cycle is detected.
        """
        if path is None:
            path = []
        if self.id in path:
            cycle = path[path.index(self.id):] + [self.id]
            raise CyclicDependencyError(cycle)
        if self.id in path:
            return
        for dep_id in self.dependencies:
            if dep_id in all_plugins:
                dep = all_plugins[dep_id]
                dep.check_cyclic_dependency(all_plugins, path + [self.id])

    def check_dependency_satisfied(
        self,
        all_plugins: dict[str, Plugin],
    ) -> list[str]:
        """Check that all required dependencies are available.

        Args:
            all_plugins: Dict of all plugin IDs to their Plugin objects.

        Returns:
            List of missing dependency IDs.
        """
        missing: list[str] = []
        for dep_id in self.dependencies:
            if dep_id not in all_plugins:
                missing.append(dep_id)
            else:
                dep = all_plugins[dep_id]
                if not dep.enabled or dep.state in (
                    PluginState.ERROR, PluginState.SHUTDOWN, PluginState.DISABLED,
                ):
                    missing.append(dep_id)
        return missing

    # ─── Queries ───────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self.state == PluginState.ACTIVE and self.enabled

    @property
    def is_error(self) -> bool:
        return self.state == PluginState.ERROR

    @property
    def is_healthy(self) -> bool:
        return self.health_status == "ok"

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities
