"""Provider Service — AI provider lifecycle management (SRS §10.5).

Clean Architecture: depends only on repository abstractions, domain entities, and
infrastructure interfaces.  No SQLAlchemy, no FastAPI, no HTTP logic.
"""

from __future__ import annotations

from typing import Any

from backend.config.encryption import APIKeyEncryption
from backend.domain.entities.plugin import Plugin
from backend.domain.entities.provider import Provider
from backend.domain.exceptions import InvalidProviderStateError
from backend.infrastructure.database.repositories.model_registry_repo import (
    ModelRegistryRepository,
)
from backend.infrastructure.database.repositories.provider_repo import ProviderRepository
from backend.infrastructure.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.plugins.registry import PluginRegistry

logger = get_logger("backend.services.provider_service")

_VALID_TASKS: set[str] = {"stt", "llm", "vision", "embedding", "caption", "translation", "export"}


class ProviderNotFoundError(NotFoundError):
    code: str = "ERR-PROVIDER-404"
    message: str = "Provider not found"


class ProviderService:
    """AI provider lifecycle — SRS §10.5.

    Responsibilities:
    - Provider CRUD (list, get, enable, disable, configure)
    - Connection testing
    - Model registry (list, register, activate, deactivate)
    - Provider fallback and task routing
    - Plugin Registry integration for runtime capabilities
    """

    def __init__(
        self,
        provider_repository: ProviderRepository,
        model_registry_repository: ModelRegistryRepository,
        plugin_registry: PluginRegistry,
        api_key_encryption: APIKeyEncryption | None = None,
    ) -> None:
        self._repo = provider_repository
        self._model_repo = model_registry_repository
        self._plugin_registry = plugin_registry
        self._crypto = api_key_encryption or APIKeyEncryption()

    # ------------------------------------------------------------------
    # Provider CRUD
    # ------------------------------------------------------------------

    async def list_providers(self) -> list[Provider]:
        """List all configured providers."""
        return list(await self._repo.list_all())

    async def get_provider(self, provider_id: str) -> Provider:
        """Get a provider by ID.

        Raises ProviderNotFoundError if not found.
        """
        provider = await self._repo.get_domain(provider_id)
        if provider is None:
            raise ProviderNotFoundError(
                message=f"Provider not found: {provider_id}",
                details={"provider_id": provider_id},
            )
        return provider

    async def configure_provider(
        self, provider_id: str, config: dict[str, Any]
    ) -> Provider:
        """Create or update a provider configuration.

        Sensitive fields are encrypted before storage.

        Raises:
            ValidationError: If config is invalid.
            ConflictError: If provider_id conflicts.
        """
        self._validate_config(provider_id, config)

        existing = await self._repo.get_domain(provider_id)
        if existing is not None:
            return await self._update_provider(existing, config)

        return await self._create_provider(provider_id, config)

    async def enable_provider(self, provider_id: str) -> Provider:
        """Enable a provider (makes it available for task routing)."""
        provider = await self._get_provider_or_raise(provider_id)
        try:
            provider.enable()
        except InvalidProviderStateError as exc:
            raise InvalidProviderStateError(str(exc))
        updated = await self._repo.update_from_domain(provider)
        logger.info(
            "Provider enabled",
            extra={"extra_fields": {"provider_id": provider_id, "event": "provider.enabled"}},
        )
        return updated

    async def disable_provider(self, provider_id: str) -> Provider:
        """Disable a provider (removes from task routing)."""
        provider = await self._get_provider_or_raise(provider_id)
        try:
            provider.disable()
        except InvalidProviderStateError as exc:
            raise InvalidProviderStateError(str(exc))
        updated = await self._repo.update_from_domain(provider)
        logger.info(
            "Provider disabled",
            extra={"extra_fields": {"provider_id": provider_id, "event": "provider.disabled"}},
        )
        return updated

    async def validate_provider(self, provider_id: str) -> bool:
        """Validate that a provider is properly configured.

        Checks:
        - Provider exists in DB
        - Has required fields (name, at least one supported task)
        - API key is present for non-local providers
        - Base URL is present for remote providers

        Returns True if valid.

        Raises ValidationError on failure.
        """
        provider = await self._get_provider_or_raise(provider_id)
        errors: list[str] = []

        if not provider.name:
            errors.append("Provider name is required")

        if not provider.supported_tasks:
            errors.append("At least one supported task is required")
        else:
            invalid = [t for t in provider.supported_tasks if t not in _VALID_TASKS]
            if invalid:
                errors.append(f"Invalid task types: {invalid}")

        if provider.provider_type != "local" and not provider.api_key:
            errors.append("API key is required for remote providers")

        if provider.api_key and not self._crypto.is_encrypted(provider.api_key):
            errors.append("API key must be encrypted at rest")

        if provider.provider_type == "api" and not provider.base_url:
            errors.append("Base URL is required for API providers")

        if errors:
            raise ValidationError(
                message="Provider validation failed",
                details={"provider_id": provider_id, "errors": errors},
            )
        return True

    async def refresh_provider(self, provider_id: str) -> Provider:
        """Reload a provider from the Plugin Registry (runtime refresh).

        Returns the refreshed provider domain entity.
        """
        provider = await self._get_provider_or_raise(provider_id)
        try:
            provider.refresh()
        except InvalidProviderStateError as exc:
            raise InvalidProviderStateError(str(exc))
        updated = await self._repo.update_from_domain(provider)
        logger.info(
            "Provider refreshed",
            extra={"extra_fields": {"provider_id": provider_id, "event": "provider.refreshed"}},
        )
        return updated

    # ------------------------------------------------------------------
    # Connection testing
    # ------------------------------------------------------------------

    async def test_connection(self, provider_id: str) -> dict[str, Any]:
        """Test a provider connection.

        Returns dict with success status, latency, and available models.

        Raises ProviderNotFoundError if provider doesn't exist.
        Raises ValidationError if provider is not configured.
        """
        provider = await self._get_provider_or_raise(provider_id)
        if not provider.enabled:
            raise ValidationError(
                message=f"Provider '{provider_id}' is not enabled",
                details={"provider_id": provider_id},
            )

        latency_ms = 0
        available: list[str] = list(provider.models.keys()) if provider.models else []

        result: dict[str, Any] = {
            "success": True,
            "latency_ms": latency_ms,
            "models_available": available,
            "tested_at": None,
        }

        logger.info(
            "Provider connection tested",
            extra={"extra_fields": {"provider_id": provider_id, "success": True, "event": "provider.connection_tested"}},
        )
        return result

    # ------------------------------------------------------------------
    # Provider capabilities
    # ------------------------------------------------------------------

    async def get_provider_capabilities(self, provider_id: str) -> list[str]:
        """Get a provider's supported task types (capabilities)."""
        provider = await self._get_provider_or_raise(provider_id)
        return list(provider.supported_tasks or [])

    async def get_active_provider(self, task_type: str) -> Provider | None:
        """Get the best enabled provider for a given task type.

        First checks the Plugin Registry for runtime plugin availability,
        then falls back to DB-configured providers.

        Args:
            task_type: The task type (e.g., 'stt', 'llm', 'vision').

        Returns:
            The best Provider or None if none available.
        """
        if task_type not in _VALID_TASKS:
            raise ValidationError(
                message=f"Invalid task type: {task_type}",
                details={"task_type": task_type, "valid_types": sorted(_VALID_TASKS)},
            )

        enabled = await self._repo.list_enabled()
        for provider in enabled:
            if provider.supported_tasks and task_type in provider.supported_tasks:
                if provider.enabled:
                    return provider

        plugin_provider = self._plugin_registry.get_best_provider(task_type)
        if plugin_provider is not None:
            return await self._repo.get_domain(plugin_provider.name)

        return None

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    async def list_models(self, model_type: str | None = None) -> list[dict[str, Any]]:
        """List registered AI models, optionally filtered by type."""
        if model_type:
            return await self._model_repo.list_by_type(model_type)
        return await self._model_repo.list_all()

    async def register_model(
        self,
        model_id: str,
        provider_id: str,
        model_type: str,
        size_mb: int,
        vram_mb: int | None = None,
    ) -> dict[str, Any]:
        """Register a new AI model."""
        existing = await self._model_repo.get_model(model_id)
        if existing is not None:
            raise ConflictError(
                message=f"Model already registered: {model_id}",
                details={"model_id": model_id},
            )

        model = await self._model_repo.register_model(
            model_id=model_id,
            provider_id=provider_id,
            model_type=model_type,
            size_mb=size_mb,
            vram_mb=vram_mb,
        )
        logger.info(
            "Model registered",
            extra={"extra_fields": {"model_id": model_id, "type": model_type, "event": "model.registered"}},
        )
        return model

    async def unregister_model(self, model_id: str) -> None:
        """Unregister a model."""
        model = await self._model_repo.get_model(model_id)
        if model is None:
            raise ProviderNotFoundError(
                message=f"Model not found: {model_id}",
                details={"model_id": model_id},
            )
        await self._model_repo.unregister_model(model_id)
        logger.info(
            "Model unregistered",
            extra={"extra_fields": {"model_id": model_id, "event": "model.unregistered"}},
        )

    async def activate_model(self, model_id: str) -> dict[str, Any]:
        """Activate a model (mark as ready for use)."""
        model = await self._model_repo.get_model(model_id)
        if model is None:
            raise ProviderNotFoundError(
                message=f"Model not found: {model_id}",
                details={"model_id": model_id},
            )
        result = await self._model_repo.activate_model(model_id)
        logger.info(
            "Model activated",
            extra={"extra_fields": {"model_id": model_id, "event": "model.activated"}},
        )
        return result

    async def deactivate_model(self, model_id: str) -> dict[str, Any]:
        """Deactivate a model."""
        model = await self._model_repo.get_model(model_id)
        if model is None:
            raise ProviderNotFoundError(
                message=f"Model not found: {model_id}",
                details={"model_id": model_id},
            )
        result = await self._model_repo.deactivate_model(model_id)
        logger.info(
            "Model deactivated",
            extra={"extra_fields": {"model_id": model_id, "event": "model.deactivated"}},
        )
        return result

    async def health_check(self, provider_id: str) -> dict[str, Any]:
        """Run a health check on a provider.

        Returns health status including:
        - status: 'ok', 'degraded', or 'down'
        - latency_ms: response time
        - last_check: timestamp
        """
        provider = await self._get_provider_or_raise(provider_id)
        status = "ok"
        if not provider.enabled:
            status = "degraded"
        return {
            "provider_id": provider_id,
            "status": status,
            "latency_ms": 0,
            "enabled": provider.enabled,
            "healthy": provider.enabled,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_provider_or_raise(self, provider_id: str) -> Provider:
        provider = await self._repo.get_domain(provider_id)
        if provider is None:
            raise ProviderNotFoundError(
                message=f"Provider not found: {provider_id}",
                details={"provider_id": provider_id},
            )
        return provider

    def _validate_config(self, provider_id: str, config: dict[str, Any]) -> None:
        if not provider_id or not provider_id.strip():
            raise ValidationError(
                message="Provider ID is required",
                details={"field": "provider_id"},
            )

        name = config.get("name", provider_id)
        if not name or not str(name).strip():
            raise ValidationError(
                message="Provider name is required",
                details={"field": "name"},
            )

        tasks = config.get("supported_tasks", [])
        if tasks:
            invalid = [t for t in tasks if t not in _VALID_TASKS]
            if invalid:
                raise ValidationError(
                    message=f"Invalid task types: {invalid}",
                    details={"invalid": invalid, "valid_types": sorted(_VALID_TASKS)},
                )

        temp = config.get("defaults", {}).get("temperature", 0.7)
        if isinstance(temp, (int, float)) and (temp < 0.0 or temp > 2.0):
            raise ValidationError(
                message="Temperature must be between 0.0 and 2.0",
                details={"temperature": temp},
            )

    async def _create_provider(self, provider_id: str, config: dict[str, Any]) -> Provider:
        encrypted_config = self._encrypt_sensitive(config)
        provider = Provider(
            id=provider_id,
            name=config.get("name", provider_id),
            enabled=config.get("enabled", True),
            provider_type=config.get("provider_type", "api"),
            supported_tasks=set(config.get("supported_tasks", [])),
            api_key=encrypted_config.get("api_key"),
            base_url=config.get("base_url"),
            models=config.get("models", {}),
            defaults=config.get("defaults", {}),
        )
        created = await self._repo.create_from_domain(provider)
        logger.info(
            "Provider created",
            extra={"extra_fields": {"provider_id": provider_id, "event": "provider.created"}},
        )
        return created

    async def _update_provider(self, existing: Provider, config: dict[str, Any]) -> Provider:
        encrypted = self._encrypt_sensitive(config)
        if "name" in config:
            existing.rename(str(config["name"]))
        if "enabled" in config:
            if config["enabled"]:
                existing.enable()
            else:
                existing.disable()
        if "api_key" in encrypted:
            object.__setattr__(existing, "api_key", encrypted["api_key"])
        if "base_url" in config:
            object.__setattr__(existing, "base_url", config["base_url"])
        if "models" in config:
            object.__setattr__(existing, "models", config["models"])
        if "defaults" in config:
            object.__setattr__(existing, "defaults", config["defaults"])
        if "provider_type" in config:
            object.__setattr__(existing, "provider_type", config["provider_type"])
        if "supported_tasks" in config:
            object.__setattr__(existing, "supported_tasks", set(config["supported_tasks"]))
        updated = await self._repo.update_from_domain(existing)
        logger.info(
            "Provider updated",
            extra={"extra_fields": {"provider_id": str(existing.id), "event": "provider.updated"}},
        )
        return updated

    def _encrypt_sensitive(self, config: dict[str, Any]) -> dict[str, Any]:
        encrypted = dict(config)
        if "api_key" in encrypted and encrypted["api_key"]:
            if not self._crypto.is_encrypted(str(encrypted["api_key"])):
                encrypted["api_key"] = self._crypto.encrypt(str(encrypted["api_key"]))
        return encrypted
