# ADR-005: REST API with FastAPI

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal Backend Engineer

---

## Context

The frontend communicates with the backend for all data operations. The API must support CRUD operations for projects, videos, clips, settings, and AI providers. It must also support file uploads for video import.

## Decision

Use RESTful API design with JSON request/response bodies. Use FastAPI's route decorators for endpoint definitions. Use Pydantic models for request/response validation.

## API Design Principles

1. **Resource-oriented** — Endpoints map to resources: `/projects`, `/videos`, `/clips`, `/exports`
2. **Versioned** — `/api/v1/` prefix for all endpoints
3. **Consistent error format** — `{"error": {"code": "ERR-XXX", "message": "...", "details": {...}}}`
4. **HTTP status codes** — Standard HTTP status codes (200, 201, 202, 204, 400, 404, 409, 413, 415, 422, 500)
5. **Request ID** — `X-Request-ID` header for request tracing

## Rationale

- REST is well-understood by frontend developers
- FastAPI's auto-generated OpenAPI provides interactive documentation
- Pydantic validation ensures type safety at API boundaries
- File uploads use multipart/form-data for video import

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| GraphQL | Over-engineered for single-user app; complex caching |
| gRPC | Requires protobuf definitions; unnecessary for localhost |
| tRPC | TypeScript-centric; Python backend is the chosen stack |
| Plain WebSocket | Over-complex for request-response; better for events only |

## Consequences

- File uploads require multipart handling (FastAPI's `UploadFile`)
- Large video uploads benefit from streaming (avoid loading into memory)
- REST statelessness is natural for single-user local app
- No rate limiting needed (localhost)

---
