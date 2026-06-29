# ADR-014: No Authentication Architecture

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal Security Engineer

---

## Context

The application serves a single user on a single local machine. The Vision Document explicitly excludes authentication, login, registration, and all multi-user infrastructure.

## Decision

The application will have zero authentication infrastructure. No login page. No session management. No API keys for the application itself. The application opens directly into the project browser.

## Implications

| Concern | Resolution |
|---------|------------|
| **Security** | Application is only accessible from localhost. No external network exposure. |
| **Data isolation** | Single user — no need to isolate data between users |
| **API access** | All API endpoints are unrestricted (by design) |
| **WebSocket** | No authentication for WebSocket connections |
| **Settings** | API key management for external AI providers is handled through encryption at rest, not authentication |
| **CORS** | CORS configured to allow only localhost origins |

## Rationale

- **No threat model** — Localhost-only application has no network attack surface
- **Zero complexity** — Authentication is the #1 source of security vulnerabilities
- **User experience** — Opens instantly; no login delay
- **Philosophical alignment** — Vision Document mandates no authentication

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Basic authentication | Adds unnecessary complexity; no benefit for localhost |
| API keys | Same issue; solves no real threat |
| Session cookies | No multi-user need; no logout concept |
| No auth (current decision) | ✓ Correct choice |

## Consequences

- Must ensure application binds only to `127.0.0.1` (not `0.0.0.0`) to prevent network access
- All auth-related code from the original Freebuff template must be removed
- No rate limiting needed (single trusted user)
- No permission system needed (single user is owner of everything)

---
