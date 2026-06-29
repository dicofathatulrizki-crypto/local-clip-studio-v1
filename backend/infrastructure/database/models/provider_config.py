"""
ProviderConfig model — stores AI provider configurations.

Each provider (OpenAI, local, Ollama, etc.) has configuration including
enabled status, encrypted API keys, and task routing preferences.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.infrastructure.database.base import Base


class ProviderConfig(Base):
    """AI provider configuration.

    Each row represents one configured AI provider (e.g., openai, local, ollama).
    Configuration values are stored as JSON and may include encrypted API keys.
    """

    __tablename__ = "provider_configs"

    # ─── Fields ────────────────────────────────────────────────
    provider_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    config: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    task_routing: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now(UTC),
        onupdate=datetime.now(UTC),
    )
