"""Provider entity — an AI provider configuration.

Represents a configured AI provider (local, OpenAI, Anthropic, Ollama, etc.)
with its settings, enabled state, and supported capabilities.

Business rules:
    - API keys are encrypted at rest (encryption happens outside domain)
    - Each provider supports specific task types (stt, llm, vision, etc.)
    - Providers can be enabled/disabled without restart
    - Fallback chains defined by task routing configuration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.domain.exceptions import DomainValidationError
from backend.domain.value_objects import ProviderId

SUPPORTED_TASK_TYPES: set[str] = {
    "stt", "llm", "vision", "embedding", "translation", "caption", "export",
}


@dataclass
class Provider:
    """An AI provider configuration.

    Attributes:
        id: Unique provider identifier (slug, e.g., 'openai', 'local').
        name: Human-readable provider name.
        enabled: Whether this provider is currently active.
        supported_tasks: Set of supported AI task types.
        configured: Whether the provider has been fully configured.
        api_key: Encrypted API key (encryption managed by infrastructure).
        base_url: Base URL for API requests.
        models: Mapping of task type to model name.
        defaults: Default parameters (temperature, max_tokens, timeout, retry_count).
        created_at: Timestamp of creation.
        updated_at: Timestamp of last update.
    """

    id: ProviderId = field(default_factory=lambda: ProviderId(""))
    name: str = ""
    enabled: bool = False
    supported_tasks: list[str] = field(default_factory=list)
    configured: bool = False
    api_key: str | None = None
    base_url: str | None = None
    models: dict[str, str] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=lambda: {
        "temperature": 0.7,
        "max_tokens": 4096,
        "timeout": 60,
        "retry_count": 3,
    })
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Validate provider invariants."""
        if not self.name:
            raise DomainValidationError("Provider name cannot be empty")
        if self.supported_tasks:
            for task in self.supported_tasks:
                if task not in SUPPORTED_TASK_TYPES:
                    raise DomainValidationError(
                        f"Unsupported task type: '{task}'",
                        {"task": task, "supported": list(SUPPORTED_TASK_TYPES)},
                    )
        temp = self.defaults.get("temperature", 0.7)
        if not (0.0 <= temp <= 2.0):
            raise DomainValidationError(
                "Temperature must be between 0.0 and 2.0",
                {"temperature": temp},
            )
        timeout = self.defaults.get("timeout", 60)
        if timeout < 1:
            raise DomainValidationError(
                "Timeout must be at least 1 second",
                {"timeout": timeout},
            )

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------

    def enable(self) -> None:
        """Enable this provider."""
        self.enabled = True
        self.updated_at = datetime.now()

    def disable(self) -> None:
        """Disable this provider."""
        self.enabled = False
        self.updated_at = datetime.now()

    def mark_configured(self) -> None:
        """Mark this provider as configured."""
        self.configured = True
        self.updated_at = datetime.now()

    def set_api_key(self, api_key: str | None) -> None:
        """Set the (already encrypted) API key."""
        self.api_key = api_key
        self.configured = api_key is not None
        self.updated_at = datetime.now()

    def set_base_url(self, base_url: str | None) -> None:
        """Set the base URL for API requests."""
        self.base_url = base_url
        self.updated_at = datetime.now()

    def set_model(self, task_type: str, model: str) -> None:
        """Set the model for a specific task type.

        Args:
            task_type: AI task type (stt, llm, vision, etc.).
            model: Model identifier (e.g., 'gpt-4o', 'whisper-large-v3').
        """
        if task_type not in SUPPORTED_TASK_TYPES:
            raise DomainValidationError(
                f"Unsupported task type: '{task_type}'",
                {"task_type": task_type, "supported": list(SUPPORTED_TASK_TYPES)},
            )
        self.models[task_type] = model
        self.updated_at = datetime.now()

    def update_defaults(self, defaults: dict[str, Any]) -> None:
        """Update default parameters (merge semantics)."""
        self.defaults.update(defaults)
        self._validate()
        self.updated_at = datetime.now()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def supports_task(self, task_type: str) -> bool:
        """Check if this provider supports the given task type."""
        return task_type in self.supported_tasks

    def get_model_for(self, task_type: str) -> str | None:
        """Get the configured model for a task type."""
        return self.models.get(task_type)
