"""
Unit tests for database engine, session management, and repository pattern.

Tests use SQLite in-memory database with async sessions.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Integer, String, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.database.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from backend.infrastructure.database.repositories.base import BaseRepository

# ─── Test Model ─────────────────────────────────────────────────


class TestModel(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Test model for repository tests."""
    __tablename__ = "test_model"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ─── Async Fixtures ─────────────────────────────────────────────


@pytest.fixture
async def memory_session() -> AsyncSession:
    """Provide an in-memory SQLite session for testing."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    session = session_factory()

    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


# ─── Base Mixin Tests ───────────────────────────────────────────


class TestUUIDMixin:
    """Test UUID primary key generation."""

    async def test_uuid_generated_auto(self, memory_session: AsyncSession) -> None:
        """UUID should be auto-generated if not provided."""
        model = TestModel(name="test", value=42)
        memory_session.add(model)
        await memory_session.flush()
        assert model.id is not None
        assert len(model.id) == 36  # UUID string format

    async def test_uuid_provided_explicit(self, memory_session: AsyncSession) -> None:
        """Custom UUID should be accepted."""
        custom_id = str(uuid.uuid4())
        model = TestModel(id=custom_id, name="test", value=42)
        memory_session.add(model)
        await memory_session.flush()
        assert model.id == custom_id


# ─── Base Repository Tests ──────────────────────────────────────


class TestBaseRepository:
    """Test generic CRUD operations via BaseRepository."""

    @pytest.fixture(autouse=True)
    async def setup(self, memory_session: AsyncSession) -> None:
        """Set up repository and sample data."""
        self.repo = BaseRepository(TestModel, memory_session)
        self.model1 = await self.repo.create(name="Alice", value=100)
        self.model2 = await self.repo.create(name="Bob", value=200)
        self.model3 = await self.repo.create(name="Charlie", value=300)

    async def test_create(self) -> None:
        """Creating a record should return it with an ID."""
        model = await self.repo.create(name="Test", value=50)
        assert model.id is not None
        assert model.name == "Test"
        assert model.value == 50

    async def test_get(self) -> None:
        """Getting a record by ID should return it."""
        found = await self.repo.get(self.model1.id)
        assert found is not None
        assert found.name == "Alice"

    async def test_get_not_found(self) -> None:
        """Getting a non-existent ID should return None."""
        found = await self.repo.get("nonexistent-id")
        assert found is None

    async def test_list(self) -> None:
        """Listing records should return all with pagination."""
        items, total = await self.repo.list()
        assert total >= 3
        assert len(items) == total

    async def test_list_with_limit(self) -> None:
        """Listing should respect limit parameter."""
        items, total = await self.repo.list(limit=2)
        assert len(items) == 2
        assert total >= 3

    async def test_list_with_filters(self) -> None:
        """Listing should apply equality filters."""
        items, total = await self.repo.list(filters={"value": 100})
        assert total == 1
        assert items[0].name == "Alice"

    async def test_find_by(self) -> None:
        """Finding by field should return matching record."""
        found = await self.repo.find_by(name="Bob")
        assert found is not None
        assert found.value == 200

    async def test_find_by_not_found(self) -> None:
        """Finding by non-existent field should return None."""
        found = await self.repo.find_by(name="NonExistent")
        assert found is None

    async def test_find_many_by(self) -> None:
        """Finding many by field should return all matches."""
        results = await self.repo.find_many_by()
        assert len(results) >= 3

    async def test_exists(self) -> None:
        """Exists should return True for existing records."""
        assert await self.repo.exists(self.model1.id) is True
        assert await self.repo.exists("nonexistent") is False

    async def test_update(self) -> None:
        """Updating a record should modify specified fields."""
        updated = await self.repo.update(self.model1.id, name="Updated Alice")
        assert updated is not None
        assert updated.name == "Updated Alice"

    async def test_update_not_found(self) -> None:
        """Updating a non-existent ID should return None."""
        updated = await self.repo.update("nonexistent", name="Test")
        assert updated is None

    async def test_delete(self) -> None:
        """Deleting a record should remove it."""
        result = await self.repo.delete(self.model3.id)
        assert result is True
        found = await self.repo.get(self.model3.id)
        assert found is None

    async def test_delete_not_found(self) -> None:
        """Deleting a non-existent ID should return False."""
        result = await self.repo.delete("nonexistent")
        assert result is False

    async def test_soft_delete(self) -> None:
        """Soft-deleting should set is_archived flag."""
        result = await self.repo.soft_delete(self.model1.id)
        assert result is True
        # Should not be found with normal get (soft-delete filter)
        found = await self.repo.get(self.model1.id)
        assert found is None

    async def test_count(self) -> None:
        """Counting should return correct total."""
        total = await self.repo.count()
        assert total >= 3

    async def test_count_with_filters(self) -> None:
        """Counting with filters should return matching count."""
        total = await self.repo.count(filters={"value": 200})
        assert total == 1
