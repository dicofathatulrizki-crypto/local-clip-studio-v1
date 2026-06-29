"""
Integration tests for database models and repositories.

Uses a temporary SQLite database to test:
- Table creation
- CRUD operations on all models
- Relationship enforcement (cascades, constraints)
- Repository pattern with real database
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.infrastructure.database.base import Base, set_sqlite_pragmas
from backend.infrastructure.database.models import (
    Analysis,
    CaptionTrack,
    ClipCandidate,
    ExportJob,
    ModelRegistry,
    ProcessingQueue,
    Project,
    ProjectVideo,
    ProviderConfig,
    SettingsEntry,
    TimelineState,
    VersionSnapshot,
    VideoMaster,
)
from backend.infrastructure.database.repositories.project_repo import ProjectRepository


# ─── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
async def db_session(tmp_path: Path) -> AsyncSession:
    """Create a temporary SQLite database and provide a session.

    Registers the SQLite pragma listener on the async engine's underlying
    sync engine to ensure PRAGMA foreign_keys=ON is applied to every
    connection (required for cascade delete and RESTRICT constraints).
    """
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)

    # Register pragma listener on the underlying sync engine
    # This ensures PRAGMA foreign_keys=ON is set on every connection,
    # even when using aiosqlite (async wrapper).
    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragmas_connect(conn: object, _record: object) -> None:
        if isinstance(conn, sqlite3.Connection):
            set_sqlite_pragmas(conn)

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
        await session.commit()
    finally:
        await session.close()
        await engine.dispose()


@pytest.fixture
async def sample_project(db_session: AsyncSession) -> Project:
    """Create a sample project for relationship tests."""
    project = Project(
        name="Test Project",
        description="A project for testing",
        storage_path="/tmp/test_project",
        last_opened_at=datetime.now(UTC),
    )
    db_session.add(project)
    await db_session.flush()
    return project


@pytest.fixture
async def sample_video(db_session: AsyncSession) -> VideoMaster:
    """Create a sample video master record."""
    video = VideoMaster(
        hash="abc123def456abc123def456abc123def456abc123def456abc123def456abc123def4",
        original_filename="test_video.mp4",
        file_size_bytes=1048576,
        duration_ms=60000,
        width=1920,
        height=1080,
        fps=29.97,
        video_codec="h264",
        audio_codec="aac",
        storage_path="/tmp/test_video.mp4",
    )
    db_session.add(video)
    await db_session.flush()
    return video


# ─── Table Creation Tests ───────────────────────────────────────


class TestTableCreation:
    """Verify all tables are created correctly."""

    async def test_all_tables_exist(self, db_session: AsyncSession) -> None:
        """All expected tables should exist in the database."""
        result = await db_session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        tables = {row[0] for row in result.fetchall()}
        expected_tables = {
            "projects",
            "video_master",
            "project_videos",
            "analyses",
            "clip_candidates",
            "timeline_states",
            "export_jobs",
            "caption_tracks",
            "processing_queue",
            "version_snapshots",
            "settings",
            "provider_configs",
            "model_registry",
        }
        for table in expected_tables:
            assert table in tables, f"Missing table: {table}"

    async def test_columns_project(self, db_session: AsyncSession) -> None:
        """Project table should have all expected columns."""
        result = await db_session.execute(
            text("PRAGMA table_info(projects)")
        )
        columns = {row[1] for row in result.fetchall()}
        expected = {
            "id", "name", "description", "created_at", "updated_at",
            "last_opened_at", "settings", "thumbnail_path", "version",
            "storage_path", "is_archived", "archived_at",
        }
        for col in expected:
            assert col in columns, f"Missing column in projects: {col}"


# ─── Project CRUD Tests ─────────────────────────────────────────


class TestProjectCRUD:
    """Test Project model CRUD operations."""

    async def test_create_project(self, db_session: AsyncSession) -> None:
        """Creating a project should persist it."""
        project = Project(
            name="New Project",
            description="Description",
            storage_path="/tmp/new_project",
        )
        db_session.add(project)
        await db_session.flush()

        result = await db_session.execute(
            select(Project).where(Project.id == project.id)
        )
        found = result.unique().scalar_one()
        assert found.name == "New Project"
        assert found.description == "Description"

    async def test_soft_delete_project(self, db_session: AsyncSession) -> None:
        """Soft-deleting a project should set is_archived flag."""
        project = Project(
            name="To Delete",
            storage_path="/tmp/to_delete",
        )
        db_session.add(project)
        await db_session.flush()

        project.soft_delete()
        await db_session.flush()

        assert project.is_archived == 1
        assert project.archived_at is not None

    async def test_restore_project(self, db_session: AsyncSession) -> None:
        """Restoring a project should clear the archived flag."""
        project = Project(
            name="To Restore",
            storage_path="/tmp/to_restore",
        )
        db_session.add(project)
        await db_session.flush()

        project.soft_delete()
        await db_session.flush()

        project.restore()
        await db_session.flush()

        assert project.is_archived == 0
        assert project.archived_at is None

    async def test_touch_project(self, db_session: AsyncSession) -> None:
        """Touching a project should update last_opened_at."""
        project = Project(
            name="To Touch",
            storage_path="/tmp/to_touch",
        )
        db_session.add(project)
        await db_session.flush()

        project.touch()
        await db_session.flush()

        assert project.last_opened_at is not None


# ─── Relationship Tests ─────────────────────────────────────────


class TestRelationships:
    """Test foreign key relationships and cascade behavior."""

    async def test_project_video_cascade(
        self, db_session: AsyncSession, sample_project: Project,
        sample_video: VideoMaster
    ) -> None:
        """Deleting a project should cascade delete project_videos."""
        pv = ProjectVideo(
            project_id=sample_project.id,
            video_id=sample_video.id,
            source_path="/tmp/test_source.mp4",
        )
        db_session.add(pv)
        await db_session.flush()

        # Delete project (should cascade to project_videos via ON DELETE CASCADE)
        await db_session.delete(sample_project)
        await db_session.flush()

        # ProjectVideo should be gone
        result = await db_session.execute(
            select(ProjectVideo).where(ProjectVideo.id == pv.id)
        )
        assert result.unique().scalar_one_or_none() is None

    async def test_video_master_protected(
        self, db_session: AsyncSession, sample_project: Project,
        sample_video: VideoMaster
    ) -> None:
        """VideoMaster should be protected by RESTRICT when referenced."""
        pv = ProjectVideo(
            project_id=sample_project.id,
            video_id=sample_video.id,
            source_path="/tmp/test_source.mp4",
        )
        db_session.add(pv)
        await db_session.flush()

        # Cannot delete VideoMaster while ProjectVideo references it
        await db_session.delete(sample_video)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        # Rollback to clear the failed transaction for future tests
        await db_session.rollback()

    async def test_timeline_one_to_one(
        self, db_session: AsyncSession, sample_project: Project
    ) -> None:
        """Each project should have exactly one timeline."""
        timeline = TimelineState(
            project_id=sample_project.id,
            tracks=[],
            markers=[],
        )
        db_session.add(timeline)
        await db_session.flush()

        # Second timeline should violate unique constraint
        timeline2 = TimelineState(
            project_id=sample_project.id,
            tracks=[],
            markers=[],
        )
        db_session.add(timeline2)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        # Rollback to clear the failed transaction for future tests
        await db_session.rollback()


# ─── Repository Tests ───────────────────────────────────────────


class TestProjectRepository:
    """Test ProjectRepository with real database."""

    @pytest.fixture(autouse=True)
    async def setup(
        self, db_session: AsyncSession
    ) -> None:
        """Set up repository and sample data."""
        self.repo = ProjectRepository(db_session)
        self.project1 = await self.repo.create(
            name="Alpha", storage_path="/tmp/alpha"
        )
        self.project2 = await self.repo.create(
            name="Beta", storage_path="/tmp/beta"
        )
        self.project3 = await self.repo.create(
            name="Gamma", storage_path="/tmp/gamma"
        )

    async def test_get_recent(self) -> None:
        """Get recent projects should return all non-archived projects."""
        recent = await self.repo.get_recent(count=10)
        assert len(recent) >= 3
        names = {p.name for p in recent}
        assert "Alpha" in names
        assert "Beta" in names
        assert "Gamma" in names

    async def test_search_by_name(self) -> None:
        """Search by name should find matches."""
        results = await self.repo.search_by_name("alpha")
        assert len(results) >= 1
        assert results[0].name == "Alpha"

    async def test_search_by_name_partial(self) -> None:
        """Partial name search should work."""
        results = await self.repo.search_by_name("bet")
        assert len(results) >= 1
        assert results[0].name == "Beta"


# ─── Model-Specific CRUD Tests ──────────────────────────────────


class TestVideoMaster:
    """Test VideoMaster model."""

    async def test_create_video_master(self, db_session: AsyncSession) -> None:
        """Creating a video master should persist all fields."""
        video = VideoMaster(
            hash="abcd" * 16,
            original_filename="test.mp4",
            file_size_bytes=1000000,
            duration_ms=30000,
            width=1920,
            height=1080,
            fps=30.0,
            video_codec="h264",
            storage_path="/tmp/test.mp4",
        )
        db_session.add(video)
        await db_session.flush()

        assert video.id is not None
        assert video.hash == "abcd" * 16


class TestAnalysis:
    """Test Analysis model."""

    async def test_create_analysis(
        self, db_session: AsyncSession, sample_project: Project,
        sample_video: VideoMaster
    ) -> None:
        """Creating analysis with JSON fields should work."""
        pv = ProjectVideo(
            project_id=sample_project.id,
            video_id=sample_video.id,
            source_path="/tmp/source.mp4",
        )
        db_session.add(pv)
        await db_session.flush()

        analysis = Analysis(
            video_id=pv.id,
            status="completed",
            transcript={"segments": [{"start_ms": 0, "text": "Hello"}]},
            keywords=["hello", "world"],
            quality_score=85,
        )
        db_session.add(analysis)
        await db_session.flush()

        assert analysis.transcript == {"segments": [{"start_ms": 0, "text": "Hello"}]}
        assert analysis.quality_score == 85

    async def test_analysis_unique_video(
        self, db_session: AsyncSession, sample_project: Project,
        sample_video: VideoMaster
    ) -> None:
        """Each video should have only one analysis."""
        pv = ProjectVideo(
            project_id=sample_project.id,
            video_id=sample_video.id,
            source_path="/tmp/source.mp4",
        )
        db_session.add(pv)
        await db_session.flush()

        a1 = Analysis(video_id=pv.id, status="pending")
        db_session.add(a1)
        await db_session.flush()

        # Second analysis for same video should violate unique constraint
        a2 = Analysis(video_id=pv.id, status="pending")
        db_session.add(a2)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        # Rollback to clear the failed transaction for future tests
        await db_session.rollback()


class TestSettings:
    """Test SettingsEntry model."""

    async def test_set_and_get(self, db_session: AsyncSession) -> None:
        """Settings should persist key-value pairs."""
        entry = SettingsEntry(key="theme", value='"dark"')
        db_session.add(entry)
        await db_session.flush()

        result = await db_session.execute(
            select(SettingsEntry).where(SettingsEntry.key == "theme")
        )
        found = result.unique().scalar_one()
        assert found.value == '"dark"'

    async def test_update_existing(self, db_session: AsyncSession) -> None:
        """Updating an existing key should work."""
        entry = SettingsEntry(key="volume", value='"0.8"')
        db_session.add(entry)
        await db_session.flush()

        entry.value = '"0.5"'
        await db_session.flush()

        result = await db_session.execute(
            select(SettingsEntry).where(SettingsEntry.key == "volume")
        )
        found = result.unique().scalar_one()
        assert found.value == '"0.5"'


class TestVersionSnapshot:
    """Test VersionSnapshot model."""

    async def test_snapshot_creation(
        self, db_session: AsyncSession, sample_project: Project
    ) -> None:
        """Creating a version snapshot should work."""
        snapshot = VersionSnapshot(
            project_id=sample_project.id,
            version_number=1,
            snapshot_path="/tmp/snapshot_v1.json",
            snapshot_type="auto",
            file_size_bytes=1024,
        )
        db_session.add(snapshot)
        await db_session.flush()

        assert snapshot.id is not None
        assert snapshot.version_number == 1


class TestProcessingQueue:
    """Test ProcessingQueue model."""

    async def test_queue_creation(
        self, db_session: AsyncSession, sample_project: Project
    ) -> None:
        """Creating a queue entry should work."""
        job = ProcessingQueue(
            project_id=sample_project.id,
            job_type="analysis",
            status="queued",
            priority=5,
        )
        db_session.add(job)
        await db_session.flush()

        assert job.id is not None
        assert job.status == "queued"
