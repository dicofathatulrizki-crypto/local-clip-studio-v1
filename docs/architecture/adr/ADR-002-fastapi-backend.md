# ADR-002: Python FastAPI Backend

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal Backend Engineer

---

## Context

The application requires a local backend server to manage video files, run AI models, coordinate processing pipelines, and serve a REST API. The backend must support GPU-accelerated AI inference, FFmpeg subprocess management, file system operations, and background job processing.

## Decision

Use Python 3.11+ with FastAPI as the backend framework. Use Uvicorn as the ASGI server.

## Rationale

- **Python** — Primary language for AI/ML ecosystem (PyTorch, Whisper, YOLO, all target models)
- **FastAPI** — Async-first, automatic OpenAPI docs, Pydantic validation, WebSocket support
- **Uvicorn** — Production-grade ASGI server with worker process management

## Key Considerations

1. **Async support** — FastAPI's async handlers prevent blocking on I/O operations
2. **Pydantic v2** — Request/response validation aligns with SRS API contracts
3. **Dependency injection** — Built-in DI system matches architecture requirements
4. **WebSocket** — Native support for real-time progress updates
5. **OpenAPI** — Auto-generated documentation; useful as local API reference

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Node.js/Express | Cannot run PyTorch or Whisper natively |
| Go | No AI ecosystem; would need FFI to Python |
| Rust | No AI ecosystem; development velocity too slow |
| Flask | Synchronous only; requires hacks for async/WebSocket |
| Django | Too heavy for single-user API; over-engineered |

## Consequences

- Must manage Python environment and dependencies
- GIL limits CPU-bound parallelism (mitigated by multiprocessing for Celery workers)
- Memory management important for long-lived ML model processes

---
