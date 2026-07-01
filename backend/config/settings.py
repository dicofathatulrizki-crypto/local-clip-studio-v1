"""Application settings using Pydantic Settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_default_storage_path() -> Path:
    """Get the default storage path based on OS convention."""
    home = Path.home()
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    else:  # Linux/macOS
        base = home
    return base / ".localclip"


class APISettings(BaseSettings):
    """API server configuration."""

    host: str = Field(default="127.0.0.1", description="API server host")
    port: int = Field(default=8765, description="API server port", ge=1024, le=65535)
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:8765"],
        description="Allowed CORS origins",
    )
    request_id_header: str = Field(default="X-Request-ID", description="Request ID header name")
    max_upload_size: int = Field(default=50 * 1024**3, description="Max upload size in bytes")
    debug: bool = Field(default=False, description="Debug mode")


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    url: str | None = Field(default=None, description="Database URL. None = use default SQLite path")
    echo: bool = Field(default=False, description="SQLAlchemy echo mode")
    pool_size: int = Field(default=5, description="Connection pool size")
    max_overflow: int = Field(default=10, description="Max overflow connections")
    backup_count: int = Field(default=10, description="Number of backups to retain")

    @property
    def effective_url(self) -> str:
        """Get the effective database URL."""
        if self.url:
            return self.url
        storage = _get_default_storage_path()
        db_path = storage / "projects" / "localclip.db"
        return f"sqlite+aiosqlite:///{db_path}"


class StorageSettings(BaseSettings):
    """Storage configuration."""

    base_path: str | None = Field(default=None, description="Base storage path. None = use default")
    per_project_source_limit: int = Field(default=200 * 1024**3, description="Per-project source limit")
    global_cache_limit: int = Field(default=50 * 1024**3, description="Global cache limit")
    model_storage_limit: int = Field(default=100 * 1024**3, description="Model storage limit")
    log_limit: int = Field(default=500 * 1024**2, description="Log storage limit")
    temp_limit: int = Field(default=20 * 1024**3, description="Temp storage limit")
    cleanup_interval_minutes: int = Field(default=60, description="Cleanup interval")

    @property
    def effective_path(self) -> Path:
        """Get the effective storage path."""
        if self.base_path:
            return Path(self.base_path)
        return _get_default_storage_path()


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="json", description="Log format: json or console")
    file_max_mb: int = Field(default=500, description="Max log file size in MB")
    retention_days: int = Field(default=30, description="Log retention in days")
    correlation_id_header: str = Field(default="X-Correlation-ID", description="Correlation ID header")


class GPUSettings(BaseSettings):
    """GPU configuration."""

    backend: str = Field(default="auto", description="GPU backend: auto, cuda, mps, rocm, cpu")
    memory_limit_mb: int | None = Field(default=None, description="GPU memory limit in MB")
    memory_headroom: float = Field(default=0.2, description="Fraction of VRAM to reserve")
    optimal_batch_size: int = Field(default=1, description="Default optimal batch size")


class QueueSettings(BaseSettings):
    """Job queue configuration."""

    broker_url: str = Field(default="filesystem://", description="Celery broker URL")
    result_backend: str | None = Field(default=None, description="Celery result backend")
    max_concurrent_jobs: int = Field(default=2, description="Max concurrent pipeline jobs")
    task_always_eager: bool = Field(default=False, description="Run tasks synchronously (for testing)")
    task_serializer: str = Field(default="json", description="Task serializer")
    result_serializer: str = Field(default="json", description="Result serializer")
    accept_content: list[str] = Field(default=["json"], description="Accepted content types")
    worker_prefetch_multiplier: int = Field(default=1, description="Worker prefetch multiplier")


class Settings(BaseSettings):
    """Root application settings."""

    model_config = SettingsConfigDict(
        env_prefix="LOCALCLIP_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="Local Clip Studio", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    environment: str = Field(default="development", description="Environment: development, production")

    api: APISettings = Field(default_factory=APISettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    gpu: GPUSettings = Field(default_factory=GPUSettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)

    _instance: ClassVar[Settings | None] = None

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        allowed = {"development", "production", "testing"}
        if v.lower() not in allowed:
            raise ValueError(f"Environment must be one of: {', '.join(allowed)}")
        return v.lower()

    @classmethod
    def get_instance(cls) -> Settings:
        """Get or create the singleton settings instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None


def get_settings() -> Settings:
    """Get application settings (FastAPI dependency)."""
    return Settings.get_instance()
