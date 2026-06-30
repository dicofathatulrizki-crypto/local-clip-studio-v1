"""Unit tests for Provider entity."""

from __future__ import annotations

import pytest

from backend.domain.entities import Provider
from backend.domain.exceptions import DomainValidationError
from backend.domain.value_objects import ProviderId


class TestProviderCreation:
    def test_create_default(self) -> None:
        provider = Provider(id=ProviderId("test"), name="Test Provider")
        assert provider.name == "Test Provider"
        assert not provider.enabled
        assert not provider.configured
        assert provider.defaults["temperature"] == 0.7

    def test_create_enabled(self) -> None:
        provider = Provider(
            id=ProviderId("openai"),
            name="OpenAI",
            enabled=True,
            supported_tasks=["llm", "stt", "vision"],
            configured=True,
        )
        assert provider.enabled
        assert provider.supported_tasks == ["llm", "stt", "vision"]

    def test_empty_name_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Provider(id=ProviderId("test"), name="")

    def test_unsupported_task_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Provider(
                id=ProviderId("test"),
                name="Test",
                supported_tasks=["invalid_task"],
            )

    def test_invalid_temperature_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Provider(
                id=ProviderId("test"),
                name="Test",
                defaults={"temperature": 3.0},
            )

    def test_invalid_timeout_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Provider(
                id=ProviderId("test"),
                name="Test",
                defaults={"timeout": 0},
            )


class TestProviderBehaviour:
    def test_enable(self) -> None:
        provider = Provider(id=ProviderId("test"), name="Test")
        assert not provider.enabled
        provider.enable()
        assert provider.enabled

    def test_disable(self) -> None:
        provider = Provider(
            id=ProviderId("test"),
            name="Test",
            enabled=True,
        )
        provider.disable()
        assert not provider.enabled

    def test_mark_configured(self) -> None:
        provider = Provider(id=ProviderId("test"), name="Test")
        assert not provider.configured
        provider.mark_configured()
        assert provider.configured

    def test_set_api_key(self) -> None:
        provider = Provider(id=ProviderId("test"), name="Test")
        provider.set_api_key("sk-encrypted")
        assert provider.api_key == "sk-encrypted"
        assert provider.configured

    def test_clear_api_key(self) -> None:
        provider = Provider(id=ProviderId("test"), name="Test")
        provider.set_api_key("sk-encrypted")
        provider.set_api_key(None)
        assert provider.api_key is None
        assert not provider.configured

    def test_set_base_url(self) -> None:
        provider = Provider(id=ProviderId("test"), name="Test")
        provider.set_base_url("https://api.example.com/v1")
        assert provider.base_url == "https://api.example.com/v1"

    def test_set_model(self) -> None:
        provider = Provider(id=ProviderId("test"), name="Test")
        provider.set_model("llm", "gpt-4o")
        assert provider.models["llm"] == "gpt-4o"

    def test_unsupported_task_model_raises(self) -> None:
        provider = Provider(id=ProviderId("test"), name="Test")
        with pytest.raises(DomainValidationError):
            provider.set_model("invalid", "model")

    def test_update_defaults(self) -> None:
        provider = Provider(id=ProviderId("test"), name="Test")
        provider.update_defaults({"temperature": 0.5, "timeout": 120})
        assert provider.defaults["temperature"] == 0.5
        assert provider.defaults["timeout"] == 120


class TestProviderQueries:
    def test_supports_task(self) -> None:
        provider = Provider(
            id=ProviderId("test"),
            name="Test",
            supported_tasks=["llm", "stt"],
        )
        assert provider.supports_task("llm")
        assert not provider.supports_task("vision")

    def test_get_model(self) -> None:
        provider = Provider(
            id=ProviderId("test"),
            name="Test",
            models={"llm": "gpt-4o"},
        )
        assert provider.get_model_for("llm") == "gpt-4o"
        assert provider.get_model_for("vision") is None
