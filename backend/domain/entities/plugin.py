"""Plugin entity — represents a plugin in the system.

A Plugin represents a loaded plugin instance with its runtime state.
``PluginInfo`` is the immutable metadata about a plugin (from its manifest).

Business rules:
    - Plugin lifecycle follows ``PluginState`` machine (SRS §11.6)
    - Each plugin has a unique name (identifier)
    - Version must follow semantic versioning
    - Permissions are declared in manifest and enforced at runtime
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.domain.exceptions import DomainValidationError
from backend.domain.state_machines import PluginState, validate_plugin_transition
from backend.domain.value_objects import PluginId


@dataclass(frozen=True)
class PluginInfo:
    """Immutable plugin metadata from the manifest.

    This is the read-only description of a plugin. It is created from
    the plugin's ``manifest.json`` and does not change during the
    application's runtime.
    """

    name: str = ""
    version: str = ""
    plugin_type: str = ""  # stt, llm, vision, caption, translation, export
    author: str = ""
    description: str = ""
    entry_point: str = ""
    capabilities: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    min_app_version: str = ""
    max_app_version: str | None = None
    models: list[dict[str, Any]] = field(default_factory=list)
    python_dependencies: list[str] = field(default_factory=list)
    checksum: str | None = None

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Validate plugin info invariants."""
        if not self.name:
            raise DomainValidationError("Plugin name cannot be empty")
        if not self.version:
            raise DomainValidationError("Plugin version cannot be empty")
        VALID_TYPES = {"stt", "llm", "vision", "caption", "translation", "export"}
        if self.plugin_type and self.plugin_type not in VALID_TYPES:
            raise DomainValidationError(
                f"Invalid plugin type: '{self.plugin_type}'",
                {"plugin_type": self.plugin_type, "valid": list(VALID_TYPES)},
            )

    @property
    def plugin_id(self) -> PluginId:
        return PluginId(value=self.name)


@dataclass
class Plugin:
    """A plugin instance with its runtime state.

    Attributes:
        info: Immutable plugin metadata from the manifest.
        state: Current lifecycle state.
        instance: Runtime plugin instance (set after loading).
        error_message: Error message if in ERROR state.
        priority: Priority for fallback ordering (0 = highest).
        health_status: Last health check result.
        loaded_at: Timestamp when the plugin was loaded.
    """

    info: PluginInfo = field(default_factory=PluginInfo)
    state: PluginState = PluginState.DISCOVERED
    instance: Any = None  # Set after loading — contains the plugin class instance
    error_message: str | None = None
    priority: int = 50  # Default priority (0 = highest, 100 = lowest)
    health_status: str = "unknown"
    loaded_at: datetime | None = None

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Validate plugin invariants."""
        if not self.info.name:
            raise DomainValidationError("Plugin must have a name")

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Transition to LOADED state."""
        validate_plugin_transition(self.state, PluginState.LOADED)
        self.state = PluginState.LOADED
        self.loaded_at = datetime.now()

    def initialize(self) -> None:
        """Transition to INITIALIZED state."""
        validate_plugin_transition(self.state, PluginState.INITIALIZED)
        self.state = PluginState.INITIALIZED

    def activate(self) -> None:
        """Transition to ACTIVE state."""
        validate_plugin_transition(self.state, PluginState.ACTIVE)
        self.state = PluginState.ACTIVE

    def shutdown(self) -> None:
        """Transition to SHUTDOWN state."""
        validate_plugin_transition(self.state, PluginState.SHUTDOWN)
        self.state = PluginState.SHUTDOWN

    def disable(self) -> None:
        """Transition to DISABLED state (terminal)."""
        validate_plugin_transition(self.state, PluginState.DISABLED)
        self.state = PluginState.DISABLED

    def mark_error(self, error_message: str) -> None:
        """Transition to ERROR state with an error message."""
        validate_plugin_transition(self.state, PluginState.ERROR)
        self.state = PluginState.ERROR
        self.error_message = error_message

    def retry(self) -> None:
        """Retry from ERROR by going back to INITIALIZED."""
        validate_plugin_transition(self.state, PluginState.INITIALIZED)
        self.state = PluginState.INITIALIZED
        self.error_message = None

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------

    def set_instance(self, instance: Any) -> None:
        """Set the runtime plugin instance after loading."""
        self.instance = instance

    def set_priority(self, priority: int) -> None:
        """Set the plugin's priority for fallback ordering.

        Args:
            priority: Priority value (0 = highest, 100 = lowest).
        """
        if not (0 <= priority <= 100):
            raise DomainValidationError(
                "Priority must be between 0 and 100",
                {"priority": priority},
            )
        self.priority = priority

    def update_health(self, status: str) -> None:
        """Update the health check result.

        Args:
            status: Health status string ('healthy', 'degraded', 'unhealthy').
        """
        self.health_status = status

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self.info.name

    @property
    def plugin_type(self) -> str:
        return self.info.plugin_type

    @property
    def version(self) -> str:
        return self.info.version

    @property
    def is_active(self) -> bool:
        return self.state == PluginState.ACTIVE

    @property
    def is_loaded(self) -> bool:
        return self.state in {PluginState.LOADED, PluginState.INITIALIZED, PluginState.ACTIVE}

    @property
    def has_error(self) -> bool:
        return self.state == PluginState.ERROR

    @property
    def is_disabled(self) -> bool:
        return self.state == PluginState.DISABLED
