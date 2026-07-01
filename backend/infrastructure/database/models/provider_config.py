"""ProviderConfig ORM model — AI provider configuration."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.engine import Base
from backend.infrastructure.database.models.base import UUIDMixin


class ProviderConfig(UUIDMixin, Base):
    """AI provider configuration — API keys, models, settings."""

    __tablename__ = "provider_configs"

    provider_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    models: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    defaults: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    supported_tasks: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
