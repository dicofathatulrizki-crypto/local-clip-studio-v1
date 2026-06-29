# ADR-006: WebSocket for Real-Time Events

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal Backend Engineer

---

## Context

The application needs to push real-time progress updates from the backend to the frontend for long-running operations: AI pipeline progress, export encoding progress, model download progress, and system status changes.

## Decision

Use WebSocket connections for real-time event push from backend to frontend. Use a channel-based subscription model for event routing.

## Architecture

- **Endpoint:** `ws://localhost:8765/api/v1/ws`
- **Channel pattern:** `projects.{project_id}`, `jobs.{job_id}`, `system`
- **Event format:** `{event_type, payload, timestamp}`
- **Keepalive:** Client sends `ping` every 30s; server closes after 120s idle

## Rationale

- **FastAPI native** — Built-in WebSocket support with `WebSocket` dependency
- **No polling** — Reduces unnecessary HTTP requests vs. polling
- **Channel isolation** — Frontend subscribes to relevant channels only
- **Localhost** — No need for message brokers (Redis pub/sub); in-process event bus is sufficient

## Events

| Direction | Event | Frequency | Payload Size |
|-----------|-------|-----------|--------------|
| Server→Client | `job.progress` | Every 1-5s | < 1 KB |
| Server→Client | `job.completed` | Once | < 5 KB |
| Server→Client | `job.failed` | Once | < 2 KB |
| Server→Client | `pipeline.stage` | Per stage transition | < 1 KB |
| Server→Client | `export.progress` | Every frame (or 100ms) | < 500 B |
| Server→Client | `model.download` | Every 1s | < 1 KB |
| Server→Client | `system.warning` | On condition | < 2 KB |
| Client→Server | `subscribe` | On connect | < 500 B |
| Client→Server | `ping` | Every 30s | < 100 B |

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| HTTP Long Polling | Higher latency; more server overhead |
| Server-Sent Events (SSE) | One-way only; client cannot send events |
| Polling (setInterval) | Wasteful for infrequent updates |
| Socket.IO | Adds protocol overhead; over-engineered for localhost |

## Consequences

- WebSocket connections consume file descriptors (acceptable for single user)
- FastAPI's WebSocket integration handles connection lifecycle
- No need for horizontal scaling (single user)
- Reconnection logic required in frontend

---
