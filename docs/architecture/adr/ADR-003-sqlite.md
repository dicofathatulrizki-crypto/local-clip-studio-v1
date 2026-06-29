# ADR-003: SQLite as Primary Database

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal Database Architect

---

## Context

The application needs persistent storage for project metadata, processing results, and configuration. As a local-first, single-user application, the database must be zero-configuration, serverless, and embedded.

## Decision

Use SQLite as the primary database. Design the schema to be PostgreSQL-compatible for users who may want to self-host with PostgreSQL.

## Rationale

- **Zero configuration** — No database server to install, configure, or maintain
- **Serverless** — Embedded in the application process
- **Single-user** — No concurrent write contention (ideal for SQLite)
- **Portable** — Database file can be backed up by copying one file
- **SQLAlchemy compatibility** — Same ORM code can target PostgreSQL with migration changes
- **Performance** — More than sufficient for single-user metadata (< 10K records per project)

## Storage Strategy

- **Project database:** One SQLite file per project at `{project_dir}/project.db`
- **Global database:** One SQLite file for global settings at `~/.localclip/config/settings.db`
- **Maximum database size:** Typically < 100 MB per project (metadata only; videos stored as files)

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| PostgreSQL | Requires server installation; over-engineered for single user |
| DuckDB | Optimized for analytics, not transactional CRUD |
| JSON file storage | No query capability, no consistency, no migrations |
| SQLite + Walrus | Walrus adds complexity; SQLite WAL mode is sufficient |

## Consequences

- SQLite's concurrent write limitation is acceptable (single user)
- Binary data (video files) stored on filesystem, not in database
- PostgreSQL compatibility requires avoiding SQLite-specific features
- WAL mode enabled for better concurrent read performance
- Foreign key enforcement must be explicitly enabled (PRAGMA foreign_keys = ON)

---
