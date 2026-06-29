# ADR-009: Local-First Application Design

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal Architect

---

## Context

The application is designed for personal use on a single machine. All processing must happen locally. Internet should only be required for optional features: model downloads and YouTube imports.

## Decision

Design the application as fully local-first with strict network isolation. No telemetry, no cloud storage, no mandatory internet connection.

## Design Rules

1. **All processing is local** — AI inference, video encoding, analysis, rendering all happen on the local machine
2. **Network is optional** — Application must start and function without network access
3. **No cloud dependency** — No cloud database, cloud storage, cloud rendering, or cloud AI
4. **No telemetry** — Zero data leaves the machine unless user configures an external AI provider
5. **API keys are local** — Stored encrypted on the filesystem, never transmitted except to the configured provider

## Rationale

- **Privacy** — User's video content never leaves their machine
- **Offline capability** — Works without internet (after model download)
- **No subscription** — No cloud costs to the user
- **Performance** — No network latency for AI operations
- **Control** — User owns all their data and processing

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Cloud-first (SaaS) | Violates project philosophy; requires auth, billing, infrastructure |
| Hybrid (local + cloud) | Adds complexity; privacy concerns; not needed for personal use |
| Edge computing | Over-engineered; single user doesn't need edge distribution |

## Consequences

- Local AI models require significant disk space (10-30 GB)
- Processing speed is limited by local hardware
- YouTube import requires opt-in internet access
- Model updates require user-initiated downloads
- No remote access to projects

---
