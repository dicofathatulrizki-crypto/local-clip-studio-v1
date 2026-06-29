# ADR-012: Celery for Background Job Queue

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal Backend Engineer

---

## Context

The application requires background processing for long-running operations: AI pipeline analysis, video export, model downloads, and storage cleanup. These operations can take minutes to hours and must not block API responses.

## Decision

Use Celery with a filesystem-based broker as the default, with optional Redis support. Use SQLite as the result backend.

## Architecture

- **Broker:** Filesystem (default) or Redis (optional)
- **Result backend:** SQLite (project database)
- **Worker concurrency:** 2 GPU workers + 2 CPU workers (default)
- **Task serialization:** JSON
- **Task routing:** by queue name (pipeline, export, import, maintenance)

## Rationale

- **Mature and proven** — Most widely used Python task queue
- **Task persistence** — Survives process restarts (broker stores pending tasks)
- **Worker scaling** — Can run multiple workers for concurrent GPU usage
- **Filesystem broker** — No Redis dependency for default setup
- **Task routing** — GPU tasks go to GPU workers; CPU tasks go to CPU workers

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Python threading (concurrent.futures) | GIL-bound; cannot use multiple GPUs |
| Multiprocessing (ProcessPoolExecutor) | No persistence, no retry, no monitoring |
| RQ (Redis Queue) | Requires Redis; less mature task features |
| Arq (Redis-based) | Redis dependency; smaller community |
| BackgroundTasks (FastAPI) | No persistence; lost on server restart |

## Consequences

- Celery adds complexity (worker processes, broker management)
- Filesystem broker is slower than Redis (acceptable for local use)
- Worker crashes must be handled (task.revoke(), monitoring)
- GPU memory must be partitioned between workers (HAL integration)

---
