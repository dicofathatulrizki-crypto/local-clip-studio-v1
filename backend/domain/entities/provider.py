"""Provider entity — represents an AI provider configuration.

Supports local AI models, Ollama, LM Studio, OpenAI, Anthropic,
Google Gemini, and other OpenAI-compatible providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.domain.exceptions import ProviderError
from backend.domain.value_objects import ProviderStatus


@dataclass
class Provider:
    """An AI service provider configuration.

    Business rules:
    - Provider ID must be non-empty and unique
    - API keys must be encrypted before storage (handled by service layer)
    - Task routing maps AI tasks to provider-specific models
    - Providers can be enabled/disabled independently
    - At least local AI models must be supported (offline-first)
    """

    # ─── Identity ──────────────────────────────────────────
    id: str = ""

    # ─── Configuration ─────────────────────────────────────
    enabled: bool = False
    provider_type: str = ""  # "local", "openai", "anthropic", "ollama", etc.
    config: dict[str, Any] = field(default_factory=dict)
    task_routing: dict[str, str] = field(default_factory=dict)

    # ─── Status ────────────────────────────────────────────
    status: ProviderStatus = ProviderStatus.DISABLED

    SUPPORTED_PROVIDER_TYPES: set[str] = {
        "local", "openai", "anthropic", "google", "ollama",
        "lm_studio", "openrouter", "groq", "nvidia_nim",
        "together", "fireworks", "deepinfra", "mistral",
    }

    SUPPORTED_TASK_TYPES: set[str] = {
        "stt", "llm", "vision", "caption", "translation", "embedding",
    }

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ProviderError("Provider ID cannot be empty")
        if self.provider_type:
            if self.provider_type not in self.SUPPORTED_PROVIDER_TYPES:
                raise ProviderError(
                    f"Unsupported provider type '{self.provider_type}'. "
                    f"Supported: {', '.join(sorted(self.SUPPORTED_PROVIDER_TYPES))}"
                )

    def enable(self) -> None:
        """Enable this provider."""
        self.enabled = True
        self.status = ProviderStatus.ENABLED

    def disable(self) -> None:
        """Disable this provider."""
        self.enabled = False
        self.status = ProviderStatus.DISABLED

    def mark_error(self) -> None:
        """Mark the provider as having an error state."""
        self.status = ProviderStatus.ERROR

    def assign_task(self, task_type: str, model_id: str) -> None:
        """Assign a model to handle a specific AI task.

        Args:
            task_type: The AI task type (stt, llm, vision, etc.)
            model_id: The model ID to use for this task
        """
        if task_type not in self.SUPPORTED_TASK_TYPES:
            raise ProviderError(
                f"Unsupported task type '{task_type}'. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_TASK_TYPES))}"
            )
        if not model_id or not model_id.strip():
            raise ProviderError(f"Model ID cannot be empty for task '{task_type}'")
        self.task_routing[task_type] = model_id

    def remove_task_assignment(self, task_type: str) -> None:
        """Remove the model assignment for a task type."""
        self.task_routing.pop(task_type, None)

    def get_model_for_task(self, task_type: str) -> str | None:
        """Get the configured model ID for a specific task.

        Args:
            task_type: The AI task type.

        Returns:
            Model ID if configured, None otherwise.
        """
        return self.task_routing.get(task_type)

    @property
    def configured_tasks(self) -> list[str]:
        """Get the list of AI tasks this provider is configured for."""
        return list(self.task_routing.keys())

    @property
    def is_available(self) -> bool:
        """Check if the provider is available for use."""
        return self.enabled and self.status == ProviderStatus.ENABLED
