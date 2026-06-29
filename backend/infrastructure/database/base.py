"""
Declarative base and common mixins for all database models.

Provides:
- UUIDMixin: auto-generated UUID primary keys (stored as TEXT for SQLite)
- TimestampMixin: created_at, updated_at with auto-update
- SoftDeleteMixin: is_archived, archived_at for soft deletion
- Base: combined declarative base with all mixins
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

# ─── SQLite Optimizations ───────────────────────────────────────


def set_sqlite_pragmas(dbapi_connection: object) -> None:
    """Configure SQLite connection pragmas for performance and safety.

    Handles both sync (sqlite3.Connection) and async (aiosqlite.Connection)
    drivers by attempting to get the underlying sqlite3 connection and
    executing pragmas. Falls back gracefully for non-SQLite connections.

    Pragmas applied:
    - WAL mode: better concurrent read performance
    - Foreign keys: enforce referential integrity
    - Busy timeout: wait 5s instead of failing immediately
    - Synchronous NORMAL: balance durability/speed
    - Cache: 64MB page cache
    - Temp store: in-memory for temp tables
    - Memory-map: 256MB for faster reads
    """
    # Try to get a raw sqlite3 connection from various driver types
    raw_conn: object | None = None

    if isinstance(dbapi_connection, sqlite3.Connection):
        raw_conn = dbapi_connection
    elif hasattr(dbapi_connection, "_connection"):
        # aiosqlite wraps sqlite3.Connection as _connection
        raw_conn = getattr(dbapi_connection, "_connection", None)
    elif hasattr(dbapi_connection, "driver_connection"):
        # Some drivers expose the underlying connection this way
        raw_conn = getattr(dbapi_connection, "driver_connection", None)

    # Fallback: try to execute pragmas on the connection directly
    # (works for any connection object that supports cursor/execute)
    target = raw_conn if isinstance(raw_conn, sqlite3.Connection) else dbapi_connection

    try:
        cursor = target.cursor()
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA cache_size = -64000")
        cursor.execute("PRAGMA temp_store = MEMORY")
        cursor.execute("PRAGMA mmap_size = 268435456")
        cursor.close()
    except Exception:
        pass  # Not a SQLite connection or pragmas not supported


@event.listens_for(Engine, "connect")
def _on_engine_connect(dbapi_connection: object, _connection_record: object) -> None:
    """Event listener that configures SQLite pragmas on every new connection.

    Registered globally on the Engine class. Fires for both sync engines
    (sqlite3.Connection) and async engines (aiosqlite.Connection wrapper).
    """
    set_sqlite_pragmas(dbapi_connection)


# ─── Declarative Base ───────────────────────────────────────────


class Base(DeclarativeBase):
    """Base class for all ORM models."""


# ─── Mixins ─────────────────────────────────────────────────────


class UUIDMixin:
    """Adds a UUID primary key column.

    Uses String(36) for SQLite compatibility.
    For PostgreSQL, change to sqlalchemy.dialects.postgresql.UUID.
    """

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )


class TimestampMixin:
    """Adds created_at and updated_at timestamp columns.

    - created_at: set on insert, never updated
    - updated_at: set on insert and updated on every row update
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now(UTC),
        server_default=func.now(),
        onupdate=datetime.now(UTC),
    )


class SoftDeleteMixin:
    """Adds soft-delete capability with is_archived flag and archived_at timestamp.

    Soft-deleted records are excluded from normal queries by the base repository.
    They can be restored by setting is_archived=False and clearing archived_at.
    """

    is_archived: Mapped[bool] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=None,
    )

    def soft_delete(self) -> None:
        """Mark this record as archived."""
        self.is_archived = True
        self.archived_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restore this record from archived state."""
        self.is_archived = False
        self.archived_at = None
