# ADR-004: SQLAlchemy 2.0 ORM

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal Backend Engineer

---

## Context

The application requires an object-relational mapper (ORM) to interact with SQLite while supporting future PostgreSQL compatibility. The ORM must support migrations, type-safe queries, and the repository pattern.

## Decision

Use SQLAlchemy 2.0 with the new-style declarative mapping (`DeclarativeBase`). Use Alembic for schema migrations.

## Rationale

- **Mature and proven** — Most widely used Python ORM; extensive documentation
- **PostgreSQL compatibility** — Same ORM code works with SQLite and PostgreSQL
- **Type safety** — SQLAlchemy 2.0 Mapped columns with full type annotations
- **Async support** — `sqlalchemy.ext.asyncio` for async database operations
- **Migration system** — Alembic auto-generation of migrations from schema changes
- **Repository pattern** — Clean separation of data access logic

## Key Patterns

```python
# ORM Model (infrastructure layer)
class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))

# Repository (infrastructure layer)
class ProjectRepository:
    async def get_by_id(self, id: str) -> Project | None: ...
    async def save(self, project: Project) -> None: ...
```

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| SQLite raw driver | No migration system, no query builder, no type safety |
| Peewee | Less mature, smaller ecosystem, no async support |
| Tortoise ORM | Smaller community, weaker PostgreSQL compatibility |
| SQLModel | Tied to FastAPI; less flexible for complex queries |

## Consequences

- Session management requires careful scoping (request-scoped sessions)
- SQLAlchemy adds some overhead for simple queries (acceptable for metadata)
- Alembic migrations must be reviewed (auto-generate is suggested, not final)
- Async session requires async drivers (aiosqlite for SQLite, asyncpg for PostgreSQL)

---
