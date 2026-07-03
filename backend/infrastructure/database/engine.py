"""Database engine and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.infrastructure.database.base import Base
from backend.infrastructure.logging.logger import get_logger

logger = get_logger("backend.infrastructure.database.engine")

_async_engine: Any = None
_sync_engine: Any = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None
_sync_session_factory: sessionmaker[Session] | None = None


def init_engine(database_url: str, echo: bool = False) -> None:
    """Initialize the database engine."""
    global _async_engine, _sync_engine, _async_session_factory, _sync_session_factory

    # Async engine
    _async_engine = create_async_engine(
        database_url,
        echo=echo,
        pool_size=5,
        max_overflow=10,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
    )

    # Sync engine (for Alembic, scripts)
    sync_url = database_url.replace("+aiosqlite", "").replace("+asyncpg", "")
    _sync_engine = create_engine(sync_url, echo=echo)

    # Session factories
    _async_session_factory = async_sessionmaker(_async_engine, expire_on_commit=False)
    _sync_session_factory = sessionmaker(_sync_engine)

    # Enable WAL mode for SQLite
    if "sqlite" in database_url:
        _enable_wal_mode(database_url)

    logger.info(f"Database engine initialized: {database_url}")


def _enable_wal_mode(database_url: str) -> None:
    """Enable WAL mode for SQLite databases."""
    if _sync_engine is None:
        return

    @event.listens_for(_sync_engine, "connect")
    def _set_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


async def create_all_tables() -> None:
    """Create all tables defined in the ORM models."""
    if _async_engine is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    async with _async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("All database tables created")


async def drop_all_tables() -> None:
    """Drop all tables (for testing)."""
    if _async_engine is None:
        raise RuntimeError("Database engine not initialized.")
    async with _async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("All database tables dropped")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, Any]:
    """Get an async database session."""
    if _async_session_factory is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    session = _async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def get_sync_session() -> Session:
    """Get a synchronous database session."""
    if _sync_session_factory is None:
        raise RuntimeError("Database engine not initialized.")
    return _sync_session_factory()


async def close_engine() -> None:
    """Close the database engine."""
    global _async_engine, _sync_engine
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
    if _sync_engine:
        _sync_engine.dispose()
        _sync_engine = None
    logger.info("Database engine closed")
