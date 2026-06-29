# ADR-010: Structured Storage Layout

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal Backend Engineer

---

## Context

The application manages multiple data categories: project files, source videos, proxy videos, AI models, cache, logs, temporary files, and exports. A clear, organized storage structure is essential for maintainability, cleanup, and user understanding.

## Decision

Use a structured directory layout under `~/.localclip/` (Linux/macOS) or `%APPDATA%/LocalClip/` (Windows) with clearly separated directories for each data category.

## Directory Structure

```
~/.localclip/
├── config/           # Settings + encrypted API keys
├── projects/         # Per-project directories
│   └── {uuid}/
│       ├── sources/  # Immutable source video files
│       ├── proxies/  # Proxy videos for timeline
│       ├── exports/  # Rendered output files
│       ├── cache/    # Processing artifacts
│       └── versions/ # Version history snapshots
├── models/           # Downloaded AI models
├── cache/            # Shared cache
├── logs/             # Structured JSON logs
├── temp/             # Temporary processing files
└── plugins/          # User-installed plugins
```

## Rationale

- **Clear separation** — Each category has dedicated directory with known cleanup policy
- **Immutable sources** — Source videos are never modified (copied on import)
- **Per-project isolation** — Each project is self-contained; easy to back up
- **Cleanup automation** — Known directories with retention policies
- **User transparency** — Users can see exactly where files are stored

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Flat directory | Chaos with mixed file types; impossible cleanup |
| Database-only storage | Video files don't belong in databases |
| Per-type grouping (all sources together) | Hard to manage per-project cleanup |

## Consequences

- Must create directory structure on first launch
- Cleanup daemon must respect per-project boundaries
- Symlinks may be useful for shared cache across projects
- Backup/restore can be per-project (copy project directory)

---
