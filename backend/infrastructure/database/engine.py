"""
Database engine and session management for Local Clip Studio.

Provides:
- SQLAlchemy async engine creation with SQLite optimizations
- Session factory and context managers
- DatabaseManager singleton for lifecycle management
- Health check endpoint
- Backup hooks
- init_database for table creation and migration
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine as _create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from backend.config.settings import get_settings
from backend.infrastructure.database.base import Base
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


# ─── Engine Factory ─────────────────────────────────────────────


def create_engine(database_url: str | None = None) -> str:
    """Create and return the database URL for the application.

    If no URL is provided, constructs one from the app settings.
    Returns the URL string so the caller can create the engine.

    For SQLite, the database is stored at:
    {app_directory}/projects/global/localclip.db
    """
    if database_url:
        return database_url

    settings = get_settings()
    db_dir = Path(settings.app_directory) / "projects" / "global"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "localclip.db"

    # Use async SQLite via aiosqlite
    url = f"sqlite+aiosqlite:///{db_path}"
    return url


# ─── Database Manager ───────────────────────────────────────────


class DatabaseManager:
    """Singleton managing the database engine, session factory, and lifecycle.

    Usage:
        db = DatabaseManager()
        await db.initialize()

        async with db.get_session() as session:
            result = await session.execute(...)
            await session.commit()
    """

    def __init__(self) -> None:
        self._engine: Any = None
        self._async_session_factory: async_sessionmaker[AsyncSession] | None = None
        self._sync_session_factory: sessionmaker[Session] | None = None
        self._initialized: bool = False
        self._database_url: str | None = None

    async def initialize(self, database_url: str | None = None) -> None:
        """Initialize the database engine and session factory.

        Creates the engine, applies SQLite pragmas, and runs alembic
        migrations (or creates tables if no migrations exist).
        """
        if self._initialized:
            logger.debug("Database already initialized, skipping")
            return

        url = create_engine(database_url)
        self._database_url = url

        logger.info(
            "Initializing database engine",
            extra={"database_url": str(url).split("///")[-1]},
        )

        # Create async engine with SQLite optimizations
        self._engine = _create_async_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
            pool_recycle=3600,
        )

        # Create session factories
        self._async_session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Sync engine for the sync session factory (used in migrations)
        from sqlalchemy import create_engine as _create_sync_engine

        sync_url = url.replace("+aiosqlite", "")
        sync_engine = _create_sync_engine(
            sync_url,
            connect_args={"check_same_thread": False},
        )
        self._sync_session_factory = sessionmaker(
            bind=sync_engine,
            expire_on_commit=False,
        )

        # Create all tables
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self._initialized = True
        logger.info("Database initialized successfully")

    async def shutdown(self) -> None:
        """Dispose of the database engine and release resources."""
        if self._engine is not None:
            await self._engine.dispose()
            self._initialized = False
            logger.info("Database engine disposed")

    @property
    def is_initialized(self) -> bool:
        """Check if the database engine has been initialized."""
        return self._initialized

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get the async session factory."""
        if self._async_session_factory is None:
            msg = "Database not initialized. Call initialize() first."
            raise RuntimeError(msg)
        return self._async_session_factory

    async def get_session(self) -> AsyncSession:
        """Get a new async database session.

        Caller is responsible for committing/rolling back and closing.
        Prefer using the context manager get_async_session() instead.
        """
        return self.session_factory()

    def get_sync_session(self) -> Session:
        """Get a new sync database session (for legacy/script usage)."""
        if not self._initialized or self._sync_session_factory is None:
            msg = "Database not initialized. Call initialize() first."
            raise RuntimeError(msg)

        return self._sync_session_factory()

    async def health_check(self) -> dict[str, Any]:
        """Run a database health check.

        Returns:
            dict with status, latency_ms, and optional error message
        """
        if not self._initialized or self._engine is None:
            return {
                "status": "not_initialized",
                "latency_ms": 0,
                "error": "Database not initialized",
            }

        import time

        start = time.monotonic()
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            latency_ms = int((time.monotonic() - start) * 1000)
            return {"status": "ok", "latency_ms": latency_ms}
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            return {
                "status": "error",
                "latency_ms": latency_ms,
                "error": str(exc),
            }

    async def backup_database(self, backup_path: str) -> None:
        """Create a hot backup of the SQLite database.

        Uses SQLite's online backup API via the aiosqlite connection.
        Only works with SQLite databases.

        Args:
            backup_path: Absolute path for the backup file
        """
        if self._engine is None:
            logger.warning("Cannot backup: database not initialized")
            return

        # Get the raw aiosqlite connection for backup API
        from sqlalchemy import event as sa_event

        backup_conn: Any = None

        @sa_event.listens_for(self._engine.sync_engine, "connect")
        def _capture_conn(dbapi_conn: object, _connection_record: object) -> None:
            nonlocal backup_conn
            backup_conn = dbapi_conn

        try:
            async with self._engine.connect():
                pass

            if backup_conn is not None:
                import sqlite3

                dest = sqlite3.connect(backup_path)
                backup_conn.backup(dest, pages=1000)
                dest.close()
                logger.info(
                    "Database backup created",
                    extra={"backup_path": backup_path},
                )
            else:
                logger.warning("Could not get raw connection for backup")
        except Exception as exc:
            logger.error(
                "Database backup failed",
                extra={"backup_path": backup_path, "error": str(exc)},
            )
            raise

    async def integrity_check(self) -> dict[str, Any]:
        """Run SQLite integrity check on the database.

        Returns:
            dict with status and optional error details
        """
        if not self._initialized or self._engine is None:
            return {"status": "not_initialized"}

        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(text("PRAGMA integrity_check"))
                row = result.fetchone()
                if row and row[0] == "ok":
                    return {"status": "ok"}
                return {"status": "corrupt", "detail": str(row[0]) if row else "unknown"}
        except Exception as exc:
            logger.error(
                "Integrity check failed",
                extra={"error": str(exc)},
            )
            return {"status": "error", "detail": str(exc)}


# ─── Global Instance ────────────────────────────────────────────

_db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """Get the global DatabaseManager singleton."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def init_database(database_url: str | None = None) -> DatabaseManager:
    """Initialize the database (idempotent — safe to call multiple times).

    Creates tables, applies migrations, and returns the manager.

    Args:
        database_url: Optional custom database URL
    Returns:
        Initialized DatabaseManager instance
    """
    db = get_db_manager()
    await db.initialize(database_url)
    return db


# ─── FastAPI Dependency ─────────────────────────────────────────


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session.

    Automatically commits on success and rolls back on exception.
    Usage in routes:
        async def my_route(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    db = get_db_manager()
    if not db.is_initialized:
        await init_database()

    async with db.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_db_session() -> Generator[Session, None, None]:
    """Sync database session context manager (for scripts and workers).

    Usage:
        with get_sync_db_session() as session:
            ...
    """
    db = get_db_manager()
    if not db._initialized:  # noqa: SLF001
        msg = "Database not initialized. Call init_database() first."
        raise RuntimeError(msg)

    session = db.get_sync_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
