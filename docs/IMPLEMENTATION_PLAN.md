# Local Clip Studio — Implementation Plan

> **Status:** DRAFT  
> **Version:** 1.0  
> **Date:** 2026-06-29  
> **Classification:** Execution Blueprint for Phase 7+ Code Generation  
> **Traceability:** Vision v2.0 → PRD v1.0 → SRS v1.0 → Architecture Blueprint → DB Design → API Spec → This Document

---

## Table of Contents

1. [Implementation Strategy](#1-implementation-strategy)
2. [Dependency Graph](#2-dependency-graph)
3. [Module Breakdown](#3-module-breakdown)
4. [Milestone Plan](#4-milestone-plan)
5. [Sprint Plan](#5-sprint-plan)
6. [File Generation Order](#6-file-generation-order)
7. [Build Order](#7-build-order)
8. [Integration Order](#8-integration-order)
9. [Testing Order](#9-testing-order)
10. [Refactoring Checkpoints](#10-refactoring-checkpoints)
11. [Context Management Strategy](#11-context-management-strategy)
12. [Risk Assessment](#12-risk-assessment)
13. [Definition of Done](#13-definition-of-done)

---

## 1. Implementation Strategy

### 1.1 Overall Approach

**Vertical slicing with horizontal foundations.** Each feature is implemented as a complete vertical slice (API → Service → Domain → Repository) while core infrastructure layers (database, HAL, logging) are built as horizontal foundations first.

### 1.2 Guiding Principles

| Principle | Application |
|-----------|-------------|
| **Interface-first** | Define interfaces/abstract classes before implementations |
| **Bottom-up construction** | Infrastructure → Domain → Services → API (each layer builds on the one below) |
| **Vertical slice delivery** | Each module is delivered as a complete, testable unit |
| **Continuous integration** | Every module must pass its tests before the next module starts |
| **No big bang integration** | Modules are integrated incrementally, never all at once |
| **Test-driven** | Tests are written alongside implementation (not after) |

### 1.3 Build Phases

```
Phase A: Foundation     Phase B: Core               Phase C: AI Pipeline      Phase D: Frontend
════════════════════    ════════════════════        ═══════════════════        ═══════════════════
• Project scaffold     • Project management        • STT integration          • Project Browser
• Database engine      • Video import/export       • Scene detection          • Timeline Editor
• HAL layer            • Basic API endpoints        • LLM integration          • Video Preview
• FFmpeg service       • Settings service           • Clip generation          • Media Browser
• Plugin registry      • Provider management        • Caption engine           • Transcript Panel
• Logging config       • Export service             • Quality scoring          • Clip Gallery
• Configuration        • Queue management          • Analysis pipeline         • Settings UI
                                                    • Translation               • Export Dialog
                                                                                • Analytics UI
```

---

## 2. Dependency Graph

### 2.1 Module Dependency Map

```
PHASE A: FOUNDATION
═══════════════════════════════════════════════════════════════════

Module A1: Project Scaffold
  └── No dependencies (foundation)
  └── Files: pyproject.toml, Makefile, README.md, .env.example, setup.sh

Module A2: Configuration System
  └── Depends on: A1 (scaffold)
  └── Files: config/settings.py, config/defaults.py, config/encryption.py

Module A3: Logging Infrastructure
  └── Depends on: A2 (config)
  └── Files: infrastructure/logging/logger.py, logging/correlation.py

Module A4: Database Engine
  └── Depends on: A2 (config)
  └── Files: infrastructure/database/engine.py, database/models/*.py, alembic/

Module A5: Filesystem Service
  └── Depends on: A2 (config)
  └── Files: infrastructure/filesystem/*.py

Module A6: Hardware Abstraction Layer
  └── Depends on: A2 (config)
  └── Files: infrastructure/hal/*.py

Module A7: FFmpeg Service
  └── Depends on: A5 (filesystem)
  └── Files: infrastructure/ffmpeg/*.py

Module A8: Plugin Registry
  └── Depends on: A5 (filesystem), A3 (logging)
  └── Files: infrastructure/plugins/registry.py, loader.py, interfaces/*.py

     │
     ▼

PHASE B: CORE APPLICATION
═══════════════════════════════════════════════════════════════════

Module B1: Domain Entities
  └── Depends on: A4 (database models as reference)
  └── Files: domain/entities/*.py, domain/value_objects/*.py, domain/events/*.py

Module B2: Database Repositories
  └── Depends on: A4 (engine), B1 (domain entities)
  └── Files: infrastructure/database/repositories/*.py

Module B3: WebSocket Manager
  └── Depends on: A3 (logging)
  └── Files: infrastructure/websocket/manager.py, handlers.py

Module B4: Queue Management (Celery)
  └── Depends on: A4 (database), A2 (config)
  └── Files: infrastructure/queue/celery_app.py, tasks/*.py

Module B5: Project Service
  └── Depends on: B2 (repositories), A5 (filesystem)
  └── Files: services/project_service.py

Module B6: Import Service
  └── Depends on: B2, A5, A7 (FFmpeg), B4 (queue)
  └── Files: services/import_service.py

Module B7: Settings Service
  └── Depends on: A2, B2
  └── Files: services/settings_service.py

Module B8: Provider Service
  └── Depends on: A8 (plugins), B2, A2
  └── Files: services/provider_service.py

Module B9: Plugin Service
  └── Depends on: A8 (plugin registry)
  └── Files: services/plugin_service.py

Module B10: API Routes (Core)
  └── Depends on: B5, B6, B7
  └── Files: api/routes/projects.py, videos.py, settings.py, system.py

Module B11: API App Factory
  └── Depends on: B10, B3 (websocket), A3 (logging)
  └── Files: api/app.py, api/middleware.py, api/deps.py

     │
     ▼

PHASE C: AI PIPELINE
═══════════════════════════════════════════════════════════════════

Module C1: Plugin Implementations (STT)
  └── Depends on: A8 (plugin interfaces), A6 (HAL)
  └── Files: infrastructure/plugins/builtins/whisperx_stt.py

Module C2: Plugin Implementations (Vision)
  └── Depends on: A8, A6
  └── Files: infrastructure/plugins/builtins/yolo_vision.py, pyscenedetect_scene.py

Module C3: Plugin Implementations (LLM)
  └── Depends on: A8, A6
  └── Files: infrastructure/plugins/builtins/llama_llm.py

Module C4: Pipeline Orchestrator
  └── Depends on: C1, C2, C3, B4 (queue), B2 (repositories)
  └── Files: services/pipeline_service.py

Module C5: Analysis Service
  └── Depends on: C4, B2
  └── Files: services/analysis_service.py

Module C6: Clip Generation Service
  └── Depends on: C4, C5, B2
  └── Files: services/clip_generation_service.py

Module C7: Caption Service
  └── Depends on: C4, B2
  └── Files: services/caption_service.py

Module C8: Export Service
  └── Depends on: A7 (FFmpeg), A6 (HAL), B2
  └── Files: services/export_service.py

Module C9: Analytics Service
  └── Depends on: C5, C6, B2
  └── Files: services/analytics_service.py

Module C10: API Routes (Pipeline)
  └── Depends on: C4-C9, B11
  └── Files: api/routes/clips.py, exports.py, analysis.py, models.py

     │
     ▼

PHASE D: FRONTEND
═══════════════════════════════════════════════════════════════════

Module D1: API Client
  └── Depends on: B11, C10 (API contracts)
  └── Files: frontend/src/api/*.ts, frontend/src/types/*.ts

Module D2: Project Browser
  └── Depends on: D1
  └── Files: frontend/src/components/project/*.tsx, store/useProjectStore.ts

Module D3: Media Panel
  └── Depends on: D1
  └── Files: frontend/src/components/media/*.tsx

Module D4: Video Preview
  └── Depends on: D1
  └── Files: frontend/src/components/preview/*.tsx

Module D5: Timeline Editor
  └── Depends on: D4, D1
  └── Files: frontend/src/components/timeline/*.tsx, store/useTimelineStore.ts

Module D6: Transcript Panel
  └── Depends on: D1
  └── Files: frontend/src/components/transcript/*.tsx

Module D7: Clip Gallery
  └── Depends on: D1
  └── Files: frontend/src/components/clips/*.tsx

Module D8: Caption Editor
  └── Depends on: D1
  └── Files: frontend/src/components/captions/*.tsx

Module D9: Export Dialog
  └── Depends on: D1
  └── Files: frontend/src/components/export/*.tsx

Module D10: Settings UI
  └── Depends on: D1
  └── Files: frontend/src/components/settings/*.tsx

Module D11: Analytics UI
  └── Depends on: D1
  └── Files: frontend/src/components/analytics/*.tsx

Module D12: Workspace Layout
  └── Depends on: D2-D11
  └── Files: frontend/src/components/workspace/*.tsx, main.tsx
```

### 2.2 Critical Path

```
A1 (Scaffold) → A2 (Config) → A4 (Database) → B1 (Domain) → B2 (Repositories)
    ↓                           ↓
A3 (Logging)                 A6 (HAL)
    ↓                           ↓
A8 (Plugins)                 A7 (FFmpeg) → C8 (Export)
    ↓                           ↓
C1 (STT) → C2 (Vision) → C3 (LLM) → C4 (Pipeline) → C5-C7 (Analysis)
    ↓
B5 (Project) → B6 (Import) → B10 (API Core)
    ↓                           ↓
B11 (App Factory)          C10 (API Pipeline)
    ↓                           ↓
D1 (API Client) → D2-D11 (Components) → D12 (Workspace)
```

**Critical path length:** A1 → A2 → A4 → B1 → B2 → B5 → B10 → B11 → D1 → D12 (10 sequential dependencies)

---

## 3. Module Breakdown

### 3.1 PHASE A: Foundation Modules

---

#### Module A1: Project Foundation (merged A2 + A3)

> **Status:** COMPLETED ✅  
> **Formal Merge:** Module A2 (Configuration System) and Module A3 (Logging Infrastructure) have been fully implemented as part of Module A1. See Architectural Decision below.

| Property | Value |
|----------|-------|
| **Responsibilities** | Project scaffold, configuration system (settings, defaults, encryption), logging infrastructure (JSON, correlation), error handling framework, API foundation (middleware, DI) |
| **Dependencies** | None |
| **Files created** | `pyproject.toml`, `Makefile`, `README.md`, `.env.example`, `.gitignore`, `scripts/setup.sh`, `scripts/dev.sh`, `scripts/download_models.sh`, `backend/__init__.py`, `backend/__main__.py`, `backend/main.py`, `backend/config/__init__.py`, `backend/config/settings.py`, `backend/config/defaults.py`, `backend/config/encryption.py`, `backend/infrastructure/__init__.py`, `backend/infrastructure/logging/__init__.py`, `backend/infrastructure/logging/logger.py`, `backend/infrastructure/logging/correlation.py`, `backend/infrastructure/errors/__init__.py`, `backend/infrastructure/errors/app_error.py`, `backend/api/__init__.py`, `backend/api/middleware.py`, `backend/api/deps.py`, `backend/domain/__init__.py`, `backend/services/__init__.py`, `docker/Dockerfile`, `docker/docker-compose.yml`, `docker/.dockerignore`, `tests/__init__.py`, `tests/conftest.py`, `tests/unit/__init__.py`, `tests/unit/test_config.py`, `tests/unit/test_encryption.py`, `tests/unit/test_logging.py`, `tests/unit/test_errors.py`, `tests/integration/__init__.py` |
| **Estimated complexity** | Low-Medium (5-7 hours) |
| **Blocked by** | Nothing |

**Architectural Decision: A2 + A3 merged into A1**
- **Rationale:** The configuration system (A2) and logging infrastructure (A3) are tightly coupled — logging depends on config for log level/format parameters. Building them as separate modules would require two sequential code-generation passes on the same files. Merging them into A1 allows:
  1. Dependency injection to work from the start (settings → logging → error handlers)
  2. Tests for config + encryption + logging + errors to be generated together
  3. Immediate verification of the complete foundation pipeline
- **Impact:** No modules were skipped. A2 and A3 are fully implemented. Dependency graph unchanged (A2 and A3 are now part of A1's scope).
- **Traceability:** A2 files = `backend/config/*`, A3 files = `backend/infrastructure/logging/*`

**Acceptance Criteria:**
- `pip install -e ".[dev]"` succeeds
- `python -c "from backend.config.settings import Settings; print('OK')"` succeeds
- `pytest tests/unit/ -x -v` passes all 42 unit tests
- `ruff check backend/` passes with no errors
- `mypy backend/` passes
- FastAPI app starts and `/health` endpoint returns 200 OK
- Docker compose builds without errors

**Required Tests:** `tests/unit/test_config.py`, `tests/unit/test_encryption.py`, `tests/unit/test_logging.py`, `tests/unit/test_errors.py`

---

#### Module A4: Database Engine

| Property | Value |
|----------|-------|
| **Responsibilities** | SQLite engine creation, session management, Alembic configuration, migration execution |
| **Dependencies** | A2 (config) |
| **Files to create** | `backend/infrastructure/database/__init__.py`, `backend/infrastructure/database/engine.py`, `backend/infrastructure/database/models/__init__.py`, `backend/infrastructure/database/models/project.py`, `backend/infrastructure/database/models/video_master.py`, `backend/infrastructure/database/models/project_video.py`, `backend/infrastructure/database/models/analysis.py`, `backend/infrastructure/database/models/clip_candidate.py`, `backend/infrastructure/database/models/timeline_state.py`, `backend/infrastructure/database/models/export_job.py`, `backend/infrastructure/database/models/caption_track.py`, `backend/infrastructure/database/models/processing_queue.py`, `backend/infrastructure/database/models/version_snapshot.py`, `backend/infrastructure/database/repositories/__init__.py`, `backend/infrastructure/database/migrations/env.py`, `backend/infrastructure/database/migrations/alembic.ini` |
| **Estimated complexity** | Medium (6-8 hours) |
| **Blocked by** | A2 |

**Acceptance Criteria:**
- Database created on first access
- All 10+ tables created with correct schema
- SQLAlchemy 2.0 models match the Database Design specification
- Alembic migrations auto-generate and apply cleanly
- Session management works with async context
- WAL mode enabled, foreign keys enforced

**Required Tests:** `tests/unit/test_database_engine.py`, `tests/integration/test_repositories.py`

---

#### Module A5: Filesystem Service

| Property | Value |
|----------|-------|
| **Responsibilities** | Application directory creation, file operations (copy, move, hash, permissions), storage management, cleanup |
| **Dependencies** | A2 (config) |
| **Files to create** | `backend/infrastructure/filesystem/__init__.py`, `backend/infrastructure/filesystem/project_dirs.py`, `backend/infrastructure/filesystem/storage_manager.py`, `backend/infrastructure/filesystem/file_ops.py` |
| **Estimated complexity** | Medium (4-6 hours) |
| **Blocked by** | A2 |

**Acceptance Criteria:**
- Directory structure created on first launch
- SHA-256 hashing works correctly
- Path traversal attacks rejected
- Storage limits tracked per category
- Auto-cleanup removes files past retention period
- File permissions set correctly (source files read-only)

**Required Tests:** `tests/unit/test_filesystem.py`, `tests/unit/test_storage_manager.py`

---

#### Module A6: Hardware Abstraction Layer

| Property | Value |
|----------|-------|
| **Responsibilities** | GPU backend detection, HAL provider interface, memory management, device selection |
| **Dependencies** | A2 (config) |
| **Files to create** | `backend/infrastructure/hal/__init__.py`, `backend/infrastructure/hal/interface.py`, `backend/infrastructure/hal/registry.py`, `backend/infrastructure/hal/memory_manager.py`, `backend/infrastructure/hal/backends/__init__.py`, `backend/infrastructure/hal/backends/cuda_provider.py`, `backend/infrastructure/hal/backends/mps_provider.py`, `backend/infrastructure/hal/backends/rocm_provider.py`, `backend/infrastructure/hal/backends/cpu_provider.py` |
| **Estimated complexity** | High (8-10 hours) |
| **Blocked by** | A2 |

**Acceptance Criteria:**
- CUDA detected when available, falls back to MPS → ROCm → CPU
- `get_device()` returns correct device string
- `to_device()` moves tensors correctly
- `get_optimal_batch_size()` returns reasonable values
- Memory cleanup frees GPU memory
- CPU provider works on any system without GPUs
- No module imports `torch.cuda` directly

**Required Tests:** `tests/unit/hal/test_hal_registry.py`, `tests/unit/hal/test_cpu_provider.py`, `tests/unit/hal/test_memory_manager.py`

---

#### Module A7: FFmpeg Service

| Property | Value |
|----------|-------|
| **Responsibilities** | FFmpeg subprocess management, command construction, progress parsing, GPU encoder selection |
| **Dependencies** | A5 (filesystem), A6 (HAL for encoder selection) |
| **Files to create** | `backend/infrastructure/ffmpeg/__init__.py`, `backend/infrastructure/ffmpeg/ffmpeg_service.py`, `backend/infrastructure/ffmpeg/ffprobe_service.py`, `backend/infrastructure/ffmpeg/commands.py`, `backend/infrastructure/ffmpeg/progress_parser.py` |
| **Estimated complexity** | High (8-10 hours) |
| **Blocked by** | A5, A6 |

**Acceptance Criteria:**
- Audio extraction: 16kHz mono WAV
- Frame extraction: 1fps JPEGs `frame_%05d.jpg`
- Proxy generation: 720p H.264, CRF 23
- Metadata extraction: all fields from Database Design
- GPU encoder selection: NVENC → VideoToolbox → software
- Progress parsing: frame count, fps, time, bitrate from stderr
- Subprocess timeout and cancellation work correctly
- Error messages from stderr parsed and formatted

**Required Tests:** `tests/unit/test_ffmpeg_service.py`, `tests/unit/test_progress_parser.py`, `tests/integration/test_ffmpeg.py` (with real FFmpeg)

---

#### Module A8: Plugin Registry

| Property | Value |
|----------|-------|
| **Responsibilities** | Plugin discovery, manifest validation, loading, registration, health checks, shutdown |
| **Dependencies** | A5 (filesystem), A3 (logging) |
| **Files to create** | `backend/infrastructure/plugins/__init__.py`, `backend/infrastructure/plugins/registry.py`, `backend/infrastructure/plugins/loader.py`, `backend/infrastructure/plugins/interfaces/__init__.py`, `backend/infrastructure/plugins/interfaces/stt_provider.py`, `backend/infrastructure/plugins/interfaces/llm_provider.py`, `backend/infrastructure/plugins/interfaces/vision_provider.py`, `backend/infrastructure/plugins/interfaces/caption_provider.py`, `backend/infrastructure/plugins/interfaces/translation_provider.py`, `backend/infrastructure/plugins/interfaces/export_provider.py` |
| **Estimated complexity** | High (8-10 hours) |
| **Blocked by** | A5, A3 |

**Acceptance Criteria:**
- Discovers plugins from builtins/ and ~/.localclip/plugins/
- Validates manifest JSON against schema
- Rejects plugins with incompatible versions
- Loads entry point and instantiates plugin class
- Registers by type in the registry
- `get_best_provider(type)` returns highest-priority active provider
- Health checks run on schedule
- Failed plugins don't crash the application

**Required Tests:** `tests/unit/test_plugin_registry.py`, `tests/unit/test_plugin_loader.py`, `tests/integration/test_plugin_lifecycle.py`

---

### 3.2 PHASE B: Core Application Modules

---

#### Module B1: Domain Entities

| Property | Value |
|----------|-------|
| **Responsibilities** | Pure domain entities, value objects, aggregates, domain events |
| **Dependencies** | A4 (database models as reference for field definitions) |
| **Files to create** | `backend/domain/__init__.py`, `backend/domain/entities/__init__.py`, `backend/domain/entities/project.py`, `backend/domain/entities/video.py`, `backend/domain/entities/clip.py`, `backend/domain/entities/transcript.py`, `backend/domain/entities/analysis.py`, `backend/domain/value_objects/__init__.py`, `backend/domain/value_objects/time_range.py`, `backend/domain/value_objects/quality_score.py`, `backend/domain/value_objects/bounding_box.py`, `backend/domain/value_objects/transcript_segment.py`, `backend/domain/aggregates/__init__.py`, `backend/domain/aggregates/project_aggregate.py`, `backend/domain/events/__init__.py`, `backend/domain/events/video_imported.py`, `backend/domain/events/analysis_completed.py`, `backend/domain/events/export_completed.py` |
| **Estimated complexity** | Medium (6-8 hours) |
| **Blocked by** | A4 |

**Acceptance Criteria:**
- All entities defined as `@dataclass` with typed fields
- Value objects are immutable (frozen=True)
- Aggregates enforce invariants (e.g., clip start < end)
- Domain events carry all necessary data
- No imports from infrastructure or framework code
- State transitions validated (e.g., can't accept already-accepted clip)

**Required Tests:** `tests/unit/domain/test_project.py`, `tests/unit/domain/test_clip.py`, `tests/unit/domain/test_quality_score.py`, `tests/unit/domain/test_time_range.py`

---

#### Module B2: Database Repositories

| Property | Value |
|----------|-------|
| **Responsibilities** | CRUD operations for all entities via SQLAlchemy |
| **Dependencies** | A4 (engine, models), B1 (domain entities) |
| **Files to create** | `backend/infrastructure/database/repositories/project_repo.py`, `backend/infrastructure/database/repositories/video_master_repo.py`, `backend/infrastructure/database/repositories/analysis_repo.py`, `backend/infrastructure/database/repositories/clip_repo.py`, `backend/infrastructure/database/repositories/export_job_repo.py`, `backend/infrastructure/database/repositories/settings_repo.py` |
| **Estimated complexity** | Medium (6-8 hours) |
| **Blocked by** | A4, B1 |

**Acceptance Criteria:**
- All CRUD operations work with SQLite
- Repository pattern: interface in domain, impl in infrastructure
- Proper session management (commit on success, rollback on error)
- Pagination and filtering for collection queries
- Domain entities correctly mapped to/from ORM models
- Performance: < 50ms for single record operations

**Required Tests:** `tests/integration/test_project_repository.py`, `tests/integration/test_video_repository.py`, `tests/integration/test_analysis_repository.py`

---

#### Module B3: WebSocket Manager

| Property | Value |
|----------|-------|
| **Responsibilities** | Connection management, channel subscription, event broadcasting |
| **Dependencies** | A3 (logging) |
| **Files to create** | `backend/infrastructure/websocket/__init__.py`, `backend/infrastructure/websocket/manager.py`, `backend/infrastructure/websocket/handlers.py` |
| **Estimated complexity** | Medium (4-6 hours) |
| **Blocked by** | A3 |

**Acceptance Criteria:**
- Accepts WebSocket connections at `/api/v1/ws`
- Channel subscription: `projects.{id}`, `system`, `jobs.{id}`
- Event broadcasting to all subscribers
- Ping/pong keepalive (30s interval, 120s timeout)
- Cleanup on disconnect
- Thread-safe connection pool

**Required Tests:** `tests/unit/test_websocket_manager.py`, `tests/integration/test_websocket.py`

---

#### Module B4: Queue Management

| Property | Value |
|----------|-------|
| **Responsibilities** | Celery configuration, task definitions, worker lifecycle, result backend |
| **Dependencies** | A4 (database), A2 (config) |
| **Files to create** | `backend/infrastructure/queue/__init__.py`, `backend/infrastructure/queue/celery_app.py`, `backend/infrastructure/queue/tasks/__init__.py`, `backend/infrastructure/queue/tasks/analysis.py`, `backend/infrastructure/queue/tasks/export.py`, `backend/infrastructure/queue/tasks/import_video.py`, `backend/infrastructure/queue/tasks/model_download.py`, `backend/infrastructure/queue/worker.py` |
| **Estimated complexity** | Medium (6-8 hours) |
| **Blocked by** | A4, A2 |

**Acceptance Criteria:**
- Celery configured with filesystem broker (default) and Redis (optional)
- Tasks defined for: import, analysis, export, model_download
- Task routing by queue name (pipeline, export, import, maintenance)
- Progress reporting via callback or database update
- Task persistence across application restarts
- Graceful worker shutdown

**Required Tests:** `tests/unit/test_celery_config.py`, `tests/integration/test_task_execution.py`

---

#### Module B5-B11: Services & API

| Module | Responsibility | Dependencies | Complexity |
|--------|---------------|--------------|------------|
| **B5: ProjectService** | CRUD, archive, restore, duplicate, recent projects | B2, A5 | Medium (4-6h) |
| **B6: ImportService** | File validation, hash dedup, copy, proxy gen | B2, A5, A7, B4 | Medium (6-8h) |
| **B7: SettingsService** | Read/write config, validation, encryption | A2, B2 | Low (2-3h) |
| **B8: ProviderService** | Provider config, test, model list, routing | A8, B2, A2 | Medium (4-6h) |
| **B9: PluginService** | Plugin CRUD, health, enable/disable | A8 | Low (2-3h) |
| **B10: API Routes** | Project, video, settings, system endpoints | B5-B9 | Medium (8-10h) |
| **B11: App Factory** | FastAPI app, middleware, DI, startup/shutdown | B10, B3, A3 | Medium (4-6h) |

**Files for B5-B11:**
- `backend/services/project_service.py` through `backend/services/plugin_service.py`
- `backend/api/routes/projects.py`, `videos.py`, `settings.py`, `system.py`, `providers.py`
- `backend/api/app.py`, `backend/api/middleware.py`, `backend/api/deps.py`

**Acceptance Criteria (all modules):**
- All endpoints return correct status codes and response schemas
- Validation errors return structured error responses
- Request ID propagated through all service calls
- Async services complete within performance targets
- All error states handled and logged

**Required Tests:** `tests/integration/test_project_api.py`, `tests/integration/test_import_api.py`, `tests/integration/test_settings_api.py`, `tests/integration/test_provider_api.py`

---

### 3.3 PHASE C: AI Pipeline Modules

---

#### Module C1: STT Plugin (Built-in)

| Property | Value |
|----------|-------|
| **Responsibilities** | WhisperX integration for speech-to-text |
| **Dependencies** | A8 (plugin interfaces), A6 (HAL) |
| **Files to create** | `backend/infrastructure/plugins/builtins/__init__.py`, `backend/infrastructure/plugins/builtins/whisperx_stt.py` |
| **Estimated complexity** | High (8-10 hours) |
| **Blocked by** | A8 |

**Acceptance Criteria:**
- Implements STTProvider interface
- Loads WhisperX model (large-v3 default)
- Transcribes audio with word-level timestamps
- Supports model selection (tiny, base, small, medium, large-v3)
- Supports language detection
- GPU acceleration via HAL
- Model caching across calls
- Memory cleanup between calls

**Required Tests:** `tests/unit/test_whisperx_plugin.py` (mocked)

---

#### Module C2: Vision Plugin (Built-in)

| Property | Value |
|----------|-------|
| **Responsibilities** | YOLO face detection, PySceneDetect scene detection |
| **Dependencies** | A8, A6 |
| **Files to create** | `backend/infrastructure/plugins/builtins/yolo_vision.py`, `backend/infrastructure/plugins/builtins/pyscenedetect_scene.py` |
| **Estimated complexity** | High (6-8 hours) |
| **Blocked by** | A8 |

**Acceptance Criteria:**
- Face detection returns bounding boxes with confidence scores
- Face tracking assigns consistent track IDs across frames
- Scene detection returns scene boundaries with type classification
- GPU acceleration via HAL

**Required Tests:** `tests/unit/test_yolo_plugin.py`, `tests/unit/test_scene_detection.py`

---

#### Module C3: LLM Plugin (Built-in)

| Property | Value |
|----------|-------|
| **Responsibilities** | Local LLM via llama.cpp for semantic analysis |
| **Dependencies** | A8, A6 |
| **Files to create** | `backend/infrastructure/plugins/builtins/llama_llm.py` |
| **Estimated complexity** | High (8-10 hours) |
| **Blocked by** | A8 |

**Acceptance Criteria:**
- Loads GGUF model via llama.cpp Python bindings
- Supports chat completion with system/user/assistant messages
- Supports streaming response
- Temperature, max_tokens, and other parameters configurable
- GPU acceleration via HAL

**Required Tests:** `tests/unit/test_llama_plugin.py` (mocked)

---

#### Module C4-C10: Pipeline Services

| Module | Responsibility | Dependencies | Complexity |
|--------|---------------|--------------|------------|
| **C4: PipelineService** | Orchestrate 8-stage pipeline, caching, progress | C1-C3, B4, B2 | High (10-12h) |
| **C5: AnalysisService** | Save/retrieve analysis results | C4, B2 | Medium (4-6h) |
| **C6: ClipGeneration** | Candidate extraction, scoring, ranking, dedup | C4, C5, B2 | High (8-10h) |
| **C7: CaptionService** | Caption generation, style application | C4, B2 | Medium (6-8h) |
| **C8: ExportService** | FFmpeg composite, GPU encoding | A7, A6, B2 | High (8-10h) |
| **C9: AnalyticsService** | Quality scores, virality, engagement | C5, C6, B2 | Medium (4-6h) |
| **C10: API Routes** | Clip, export, analysis, model endpoints | C4-C9, B11 | Medium (6-8h) |

**Acceptance Criteria:**
- Full pipeline runs end-to-end (import → analyze → clip → export)
- Pipeline progress reported via WebSocket
- Cache hit avoids re-processing
- Cancellation stops pipeline within 5 seconds
- Quality score formula matches SRS §8 specification
- Export uses correct GPU encoder

**Required Tests:** `tests/integration/test_pipeline_api.py`, `tests/unit/test_quality_scorer.py`, `tests/unit/test_clip_generator.py`

---

### 3.4 PHASE D: Frontend Modules

| Module | Responsibility | Files | Complexity |
|--------|---------------|-------|------------|
| **D1: API Client** | Axios client, typed API functions, WebSocket hook | `api/client.ts`, `api/projects.ts`, `api/videos.ts`, `api/clips.ts`, `api/exports.ts`, `api/providers.ts`, `api/settings.ts`, `api/websocket.ts`, `types/*.ts` | Medium (6-8h) |
| **D2: Project Browser** | Project grid, create/open, recent list, empty state | `components/project/ProjectBrowser.tsx`, `components/project/ProjectCard.tsx` | Medium (4-6h) |
| **D3: Media Panel** | Media list, import dialog, progress, drag-drop zone | `components/media/MediaBrowser.tsx`, `components/media/ImportDialog.tsx` | Medium (4-6h) |
| **D4: Video Preview** | Video player, caption overlay, play/pause/seek | `components/preview/Preview.tsx`, `components/preview/CaptionOverlay.tsx` | Medium (4-6h) |
| **D5: Timeline Editor** | Multi-track, waveform, split/trim, markers, keyboard shortcuts | `components/timeline/Timeline.tsx`, `TimelineTrack.tsx`, `TimelineClip.tsx`, `Waveform.tsx`, `TimeRuler.tsx`, `Playhead.tsx`, `store/useTimelineStore.ts` | Very High (16-20h) |
| **D6: Transcript Panel** | Segment list, word highlighting, search, text-based editing | `components/transcript/TranscriptPanel.tsx`, `TranscriptSegment.tsx`, `SearchTranscript.tsx` | Medium (6-8h) |
| **D7: Clip Gallery** | Ranked clip grid, accept/reject, preview, details | `components/clips/ClipGallery.tsx`, `components/clips/ClipCard.tsx` | Medium (4-6h) |
| **D8: Caption Editor** | Style presets, font picker, animation editor | `components/captions/CaptionEditor.tsx`, `StylePresets.tsx`, `FontPicker.tsx` | Medium (6-8h) |
| **D9: Export Dialog** | Format/preset selection, progress, output path | `components/export/ExportDialog.tsx` | Low (2-4h) |
| **D10: Settings UI** | All settings panels with forms | `components/settings/SettingsDialog.tsx`, `GeneralSettings.tsx`, `Appearance.tsx`, `Storage.tsx`, `GPU.tsx`, `AIProviders.tsx`, `APIKeys.tsx`, `ExportSettings.tsx`, `KeyboardShortcuts.tsx` | Medium (8-10h) |
| **D11: Analytics UI** | Quality gauge, engagement charts, emotion timeline | `components/analytics/QualityScore.tsx`, `ViralityGraph.tsx`, `EmotionTimeline.tsx` | Medium (4-6h) |
| **D12: Workspace** | Main layout, panels, themes, keyboard shortcuts | `components/workspace/Workspace.tsx`, `Panel.tsx`, `StatusBar.tsx`, `main.tsx` | Medium (6-8h) |

---

## 4. Milestone Plan

### Milestone M1: Foundation (Days 1-5)

**Goal:** Project scaffolded, dependencies installed, core infrastructure running.

| Day | Sprint | Modules | Deliverable |
|-----|--------|---------|-------------|
| 1 | Sprint 1 | A1, A2 | Project scaffold, config system |
| 2 | Sprint 1 | A3, A4 | Logging, database engine + models |
| 3 | Sprint 2 | A5, A6 | Filesystem service, HAL (CPU only initially) |
| 4 | Sprint 2 | A7 | FFmpeg service |
| 5 | Sprint 2 | A8 | Plugin registry + interfaces |

**Verification:** `make dev` starts successfully. Database created. Plugin registry discovers built-in interfaces. FFmpeg extracts metadata from test video.

---

### Milestone M2: Core API (Days 6-10)

**Goal:** Backend running with project/video/settings APIs. Can import video and save projects.

| Day | Sprint | Modules | Deliverable |
|-----|--------|---------|-------------|
| 6 | Sprint 3 | B1, B2 | Domain entities, repositories |
| 7 | Sprint 3 | B3, B4 | WebSocket manager, queue setup |
| 8 | Sprint 4 | B5, B6 | Project service, import service |
| 9 | Sprint 4 | B7, B8, B9 | Settings, provider, plugin services |
| 10 | Sprint 5 | B10, B11 | API routes + app factory |

**Verification:** `POST /api/v1/projects` creates project. `POST /videos` imports video. `GET /system/health` returns GPU info. WebSocket connection established.

---

### Milestone M3: AI Pipeline (Days 11-16)

**Goal:** Full AI pipeline running — import → analyze → clip → export.

| Day | Sprint | Modules | Deliverable |
|-----|--------|---------|-------------|
| 11 | Sprint 5 | C1 | STT plugin (WhisperX) |
| 12 | Sprint 6 | C2 | Vision plugin (YOLO + PySceneDetect) |
| 13 | Sprint 6 | C3 | LLM plugin (llama.cpp) |
| 14 | Sprint 7 | C4, C5 | Pipeline orchestrator, analysis service |
| 15 | Sprint 7 | C6, C7, C9 | Clip generation, captions, analytics |
| 16 | Sprint 8 | C8, C10 | Export service, pipeline API routes |

**Verification:** Full pipeline runs on a 5-minute test video. Transcript generated. Clips created. MP4 exports correctly. WebSocket reports progress.

---

### Milestone M4: Frontend MVP (Days 17-23)

**Goal:** Functional desktop-like UI — project browser, timeline, preview, transcript.

| Day | Sprint | Modules | Deliverable |
|-----|--------|---------|-------------|
| 17 | Sprint 8 | D1 | API client, types, WebSocket hook |
| 18 | Sprint 9 | D2, D3 | Project browser, media panel |
| 19 | Sprint 9 | D4, D5 start | Video preview, timeline skeleton |
| 20 | Sprint 10 | D5 finish | Timeline editor with split/trim/waveform |
| 21 | Sprint 10 | D6, D7 | Transcript panel, clip gallery |
| 22 | Sprint 11 | D8, D9 | Caption editor, export dialog |
| 23 | Sprint 11 | D10, D11 | Settings UI, analytics UI |

**Verification:** User can import video → see transcript → edit timeline → add captions → export. All API calls work end-to-end.

---

### Milestone M5: Polish & Integration (Days 24-28)

**Goal:** Complete application with studio theme, keyboard shortcuts, error handling, and testing.

| Day | Sprint | Modules | Deliverable |
|-----|--------|---------|-------------|
| 24 | Sprint 12 | D12 | Workspace layout, panel management |
| 25 | Sprint 12 | Theme | Studio theme (dark/light), visual polish |
| 26 | Sprint 12 | Keyboard | Keyboard shortcut system |
| 27 | Sprint 13 | Testing | Full test suite, benchmarks |
| 28 | Sprint 13 | Bug fixes | Integration fixes, edge case handling |

**Verification:** All quality gates pass. All tests pass. Performance benchmarks meet targets. App opens directly into project browser (no auth). Dark studio theme active.

---

## 5. Sprint Plan

### 5.1 Sprint Structure

| Parameter | Value |
|-----------|-------|
| **Sprint length** | 1 day (8 working hours for AI agent) |
| **Sprints total** | 13 |
| **Vertical slices** | Each sprint delivers a vertical slice when possible |
| **Definition of Done** | All DoD checks pass (see §13) |

### 5.2 Sprint Allocation

```
Sprint 1  (Day 1-2):   A1 (Scaffold), A2 (Config), A3 (Logging), A4 (DB Engine start)
Sprint 2  (Day 3-5):   A4 (DB models), A5 (Filesystem), A6 (HAL), A7 (FFmpeg), A8 (Plugins)
Sprint 3  (Day 6-7):   B1 (Domain), B2 (Repositories), B3 (WebSocket), B4 (Queue)
Sprint 4  (Day 8-9):   B5 (Project), B6 (Import), B7 (Settings), B8 (Provider), B9 (Plugin)
Sprint 5  (Day 10-11): B10 (API Routes), B11 (App Factory), C1 (STT Plugin)
Sprint 6  (Day 12-13): C2 (Vision Plugin), C3 (LLM Plugin)
Sprint 7  (Day 14-15): C4 (Pipeline), C5 (Analysis), C6 (Clip Gen), C7 (Captions), C9 (Analytics)
Sprint 8  (Day 16-17): C8 (Export), C10 (API Pipeline), D1 (API Client frontend)
Sprint 9  (Day 18-19): D2 (Project Browser), D3 (Media Panel), D4 (Preview)
Sprint 10 (Day 20-21): D5 (Timeline Editor)
Sprint 11 (Day 22-23): D6 (Transcript), D7 (Clips Gallery), D8 (Captions), D9 (Export)
Sprint 12 (Day 24-25): D10 (Settings), D11 (Analytics), D12 (Workspace), Theme
Sprint 13 (Day 26-28): Testing, polish, bug fixes, performance tuning
```

---

## 6. File Generation Order

Backend files are generated in this strict order within each module:

### 6.1 Backend Generation Order

```
1.  backend/__init__.py
2.  backend/main.py                                    (entry point skeleton)
3.  backend/config/__init__.py, settings.py, defaults.py, encryption.py
4.  backend/infrastructure/logging/__init__.py, logger.py, correlation.py
5.  backend/infrastructure/database/engine.py           (session management)
6.  backend/infrastructure/database/models/__init__.py  (base + all models)
7.  backend/infrastructure/database/repositories/*.py   (all repos)
8.  backend/infrastructure/filesystem/*.py
9.  backend/infrastructure/hal/interface.py
10. backend/infrastructure/hal/backends/*.py
11. backend/infrastructure/hal/registry.py, memory_manager.py
12. backend/infrastructure/ffmpeg/ffprobe_service.py
13. backend/infrastructure/ffmpeg/commands.py
14. backend/infrastructure/ffmpeg/progress_parser.py
15. backend/infrastructure/ffmpeg/ffmpeg_service.py
16. backend/infrastructure/plugins/interfaces/*.py      (all interfaces)
17. backend/infrastructure/plugins/registry.py
18. backend/infrastructure/plugins/loader.py
19. backend/domain/entities/*.py
20. backend/domain/value_objects/*.py
21. backend/domain/aggregates/*.py
22. backend/domain/events/*.py
23. backend/infrastructure/websocket/manager.py
24. backend/infrastructure/websocket/handlers.py
25. backend/infrastructure/queue/celery_app.py
26. backend/infrastructure/queue/tasks/*.py
27. backend/services/project_service.py
28. backend/services/import_service.py
29. backend/services/settings_service.py
30. backend/services/provider_service.py
31. backend/services/plugin_service.py
32. backend/api/routes/projects.py
33. backend/api/routes/videos.py
34. backend/api/routes/settings.py
35. backend/api/routes/system.py
36. backend/api/routes/providers.py
37. backend/api/app.py, middleware.py, deps.py
38. backend/infrastructure/plugins/builtins/whisperx_stt.py
39. backend/infrastructure/plugins/builtins/yolo_vision.py
40. backend/infrastructure/plugins/builtins/pyscenedetect_scene.py
41. backend/infrastructure/plugins/builtins/llama_llm.py
42. backend/services/pipeline_service.py
43. backend/services/analysis_service.py
44. backend/services/clip_generation_service.py
45. backend/services/caption_service.py
46. backend/services/export_service.py
47. backend/services/analytics_service.py
48. backend/api/routes/clips.py
49. backend/api/routes/exports.py
50. backend/api/routes/analysis.py
51. backend/api/routes/models.py
52. tests/unit/* (in parallel with modules)
53. tests/integration/* (after modules)
54. tests/e2e/* (after integration)
```

### 6.2 Frontend Generation Order

```
1.  frontend/src/types/*.ts
2.  frontend/src/api/client.ts
3.  frontend/src/api/projects.ts, videos.ts, clips.ts, exports.ts, providers.ts, settings.ts
4.  frontend/src/api/websocket.ts
5.  frontend/src/store/useProjectStore.ts
6.  frontend/src/components/project/ProjectBrowser.tsx, ProjectCard.tsx
7.  frontend/src/components/media/MediaBrowser.tsx, ImportDialog.tsx
8.  frontend/src/components/preview/Preview.tsx, CaptionOverlay.tsx
9.  frontend/src/store/useTimelineStore.ts
10. frontend/src/components/timeline/Timeline.tsx, TimelineTrack.tsx, TimelineClip.tsx
11. frontend/src/components/timeline/Waveform.tsx, TimeRuler.tsx, Playhead.tsx
12. frontend/src/components/transcript/TranscriptPanel.tsx, TranscriptSegment.tsx
13. frontend/src/components/clips/ClipGallery.tsx, ClipCard.tsx
14. frontend/src/components/captions/CaptionEditor.tsx, StylePresets.tsx, FontPicker.tsx
15. frontend/src/components/export/ExportDialog.tsx
16. frontend/src/components/settings/SettingsDialog.tsx + all sub-panels
17. frontend/src/components/analytics/QualityScore.tsx, ViralityGraph.tsx, EmotionTimeline.tsx
18. frontend/src/components/workspace/Workspace.tsx, Panel.tsx, StatusBar.tsx
19. frontend/src/hooks/useTimeline.ts, useWebSocket.ts, useKeyboard.ts, etc.
20. frontend/src/index.css (theme tokens)
21. frontend/src/main.tsx (app bootstrap)
```

---

## 7. Build Order

```
Step 1: Backend foundation (A1-A8)
  Install: pip install -e ".[dev]"
  Verify: python -c "from backend.config.settings import Settings; print('OK')"
  Verify: alembic upgrade head
  Verify: pytest tests/unit/test_config.py tests/unit/test_logging.py

Step 2: Backend core (B1-B11)
  Install: (no new deps)
  Verify: pytest tests/unit/ -x
  Verify: pytest tests/integration/ -x (requires running backend)

Step 3: Backend pipeline (C1-C10)
  Install: pip install -r requirements-ai.txt (WhisperX, YOLO, llama.cpp)
  Verify: pytest tests/unit/ -x
  Verify: pytest tests/integration/ -x (with mocked models)

Step 4: Frontend (D1-D12)
  Install: bun install
  Build: bun run build
  Verify: bun tsc --noEmit

Step 5: Integration
  Start: make dev
  Test: End-to-end test suite
  Verify: All quality gates pass
```

---

## 8. Integration Order

```
Integration Point 1 (End of Sprint 2):
  └── Database + Filesystem + FFmpeg working together
  └── Test: Import a video file, verify DB record + file copy

Integration Point 2 (End of Sprint 5):
  └── Full backend API serving requests
  └── Test: POST project → POST video → GET video → DELETE video → DELETE project

Integration Point 3 (End of Sprint 8):
  └── Full AI pipeline connected to API
  └── Test: Import → Analyze → Get clips → Export (all via API)

Integration Point 4 (End of Sprint 11):
  └── Frontend connected to backend
  └── Test: Open app → create project → import video → see transcript → generate clips → export

Integration Point 5 (End of Sprint 13):
  └── Complete system with all features
  └── Test: All E2E tests pass
```

---

## 9. Testing Order

### 9.1 Test Execution Order

```
Phase A (Foundation):
  1. Unit tests for each module immediately after creation
  2. No integration tests until A4 (database) is complete

Phase B (Core):
  1. Unit tests for services (mocked repositories)
  2. Integration tests for repositories (real SQLite)
  3. Integration tests for API endpoints (real backend)

Phase C (Pipeline):
  1. Unit tests for pipeline orchestrator (mocked plugins)
  2. Unit tests for quality scorer (deterministic, no models needed)
  3. Integration tests with mocked AI models
  4. Performance benchmarks

Phase D (Frontend):
  1. Component unit tests (React Testing Library)
  2. Store tests (Zustand)
  3. API client tests (mocked fetch)
  4. Visual regression tests (Storybook)
```

### 9.2 Testing Milestones

| Milestone | Test Type | Count (Target) |
|-----------|-----------|----------------|
| M1 (Foundation) | Unit | 20+ |
| M2 (Core API) | Unit + Integration | 50+ |
| M3 (Pipeline) | Unit + Integration + Performance | 80+ |
| M4 (Frontend) | Unit + Visual | 120+ |
| M5 (Polish) | E2E + Regression | 150+ |

---

## 10. Refactoring Checkpoints

| Checkpoint | Sprint | Trigger | Action |
|------------|--------|---------|--------|
| **CP1** | After Sprint 3 | First 7 modules complete | Review: Is the repository pattern correct? Are domain entities pure? |
| **CP2** | After Sprint 5 | Core API running | Review: API response format consistency. Error handling coverage. |
| **CP3** | After Sprint 7 | Pipeline orchestrator | Review: Is the plugin architecture clean? Are fallbacks working? |
| **CP4** | After Sprint 11 | Frontend connected | Review: API contract alignment. Shared types between frontend/backend. |
| **CP5** | Final | Pre-release | Full architecture compliance review against Architecture Blueprint. |

**Each checkpoint must verify:**
1. Layer isolation intact (domain has no infrastructure imports)
2. No circular dependencies
3. Error catalog coverage ≥ 90%
4. Logging coverage on all service methods
5. No dead code or commented-out code
6. All new modules have corresponding tests

---

## 11. Context Management Strategy

### 11.1 AI-Assisted Development Guidelines

Since this project will be developed using AI code generation (Codebuff/Buffy), the following context management strategy ensures consistent, high-quality output:

| Strategy | Detail |
|----------|--------|
| **Single module per session** | Each AI session focuses on one module at a time |
| **Full context load** | Always load relevant documents (Architecture Blueprint, DB Design, API Spec) before generating code |
| **Interface-first prompt** | Start each module by loading its interface file, then generate implementation |
| **Test alongside code** | Generate tests in the same session as the implementation |
| **Strict file ordering** | Follow the file generation order in §6 — never skip ahead |
| **Validation after each file** | Run type checks and syntax validation after every 3-5 files |
| **Reference documents** | Keep these documents open in context at all times: Architecture Blueprint §3, §5, §11; API Spec §3; DB Design §4 |

### 11.2 Prompt Template for Each Module

When starting code generation for a module:

```
CONTEXT: Architecture Blueprint §3 (Module Decomposition)
         Database Design §4 (Schema)
         API Specification §3 (Endpoints)
         Implementation Plan §3 (This module's spec)

MODULE: {module_name}
TASK: Implement {module_name} following:
  - Architecture layering from Blueprint §4.2
  - Repository pattern from Blueprint §10.3
  - Coding standards from Blueprint §11
  - Error handling from Blueprint §10.3

FILES TO CREATE (in order):
  {file_list}

ACCEPTANCE CRITERIA:
  {acceptance_criteria}

DELIVER: Complete implementation + unit tests for all files.
```

### 11.3 Hot-Reload Friendly Development

```
Backend: uvicorn with --reload
Frontend: Vite dev server (HMR)
Workflow: Change code → auto-reload → verify → next module
```

---

## 12. Risk Assessment

### 12.1 Risk Matrix

| ID | Risk | Likelihood | Impact | Mitigation | Contingency |
|----|------|-----------|--------|------------|-------------|
| R1 | **GPU OOM during pipeline** | High | High | HAL memory management, configurable limits, CPU fallback | Pipeline retries with smaller models |
| R2 | **WhisperX dependency issues** | Medium | High | Pin versions, document installation, test with CPU fallback | Use faster-whisper as backup |
| R3 | **FFmpeg version incompatibility** | Medium | Medium | Pin minimum version in docs, test on macOS/Linux/Windows | Write version detection + compatibility mode |
| R4 | **PyTorch installation complexity** | Medium | Medium | Provide clear install instructions per OS, support CPU-only | Docker image with pre-installed PyTorch |
| R5 | **Timeline performance in browser** | High | Medium | Proxy editing, Canvas rendering, virtualization | WebGL-based rendering |
| R6 | **Large video import time** | Medium | Medium | Async import with progress, proxy generation in background | Show progress bar, allow cancellation |
| R7 | **LLM hallucination in analysis** | Medium | Medium | Confidence scores, user review of AI output | Allow manual override of all AI decisions |
| R8 | **Plugin security (malicious plugin)** | Low | High | Manifest validation, permission system | Subprocess sandboxing |
| R9 | **Database corruption** | Low | Critical | WAL mode, integrity checks, backups | Restore from version history |
| R10 | **Single AI session context limit** | High | Medium | Follow context preservation strategies above | Split large modules into sub-modules |

### 12.2 Architectural Risk Mitigations

| Risk Area | Mitigation Built Into Architecture |
|-----------|-----------------------------------|
| **GPU compatibility** | HAL abstraction (A6) — switch backends without code changes |
| **AI provider dependency** | Plugin system (A8) — swap providers without restart |
| **Data loss** | Version snapshots + auto-save + integrity checks |
| **Performance bottlenecks** | Proxy editing + caching + background queue |
| **Security** | Localhost-only + encrypted API keys + path traversal protection |

---

## 13. Definition of Done (DoD)

### 13.1 Module DoD

Every module must pass ALL of the following before it is considered "Done":

| # | Criterion | Verification |
|---|-----------|-------------|
| 1 | **Code complete** | All files in the module spec exist and are not empty |
| 2 | **Compiles/type-checks** | `mypy --strict` passes for the module (or `tsc --noEmit` for frontend) |
| 3 | **Unit tests pass** | All unit tests for the module pass |
| 4 | **Integration tests pass** | All integration tests for the module pass (if applicable) |
| 5 | **Error handling** | All error paths are handled (no bare `except:`) |
| 6 | **Logging** | All service methods have at least `info` level logging |
| 7 | **No lint errors** | `ruff check` passes (or `eslint` for frontend) |
| 8 | **Architecture compliance** | Module follows its layer's dependency rules (domain → nothing, service → domain + infra interfaces) |
| 9 | **No TODOs or FIXMEs** | Code has no unresolved todo comments |
| 10 | **Documentation up to date** | Docstrings exist on public methods |

### 13.2 Sprint DoD

| # | Criterion |
|---|-----------|
| 1 | All planned modules for this sprint meet Module DoD |
| 2 | Sprint integration test passes (modules work together) |
| 3 | No regression in previously completed modules |
| 4 | Error catalog updated with any new error codes |

### 13.3 Release DoD (Milestone M5)

| # | Criterion | Target |
|---|-----------|--------|
| 1 | All 13 sprints complete | ✅ |
| 2 | Test coverage ≥ 80% | Lines covered |
| 3 | All quality gates pass | 10/10 |
| 4 | Performance benchmarks meet targets | From SRS §15 |
| 5 | E2E test suite passes | 10+ workflows |
| 6 | No known critical bugs | Severity ≥ High fixed |
| 7 | Documentation complete | Vision, PRD, SRS, Architecture, DB Design, API Spec, Implementation Plan |
| 8 | Studio theme implemented | Dark + light mode |
| 9 | Application opens directly into project browser | No auth screens |

---

## Appendix: Module Complexity Summary

| Module | Complexity | Est. Hours | Dependencies | Blocked By |
|--------|-----------|------------|--------------|------------|
| A1: Scaffold | Low | 1-2 | None | — |
| A2: Config | Low | 2-3 | A1 | — |
| A3: Logging | Low | 1-2 | A2 | — |
| A4: Database | Medium | 6-8 | A2 | — |
| A5: Filesystem | Medium | 4-6 | A2 | — |
| A6: HAL | High | 8-10 | A2 | — |
| A7: FFmpeg | High | 8-10 | A5, A6 | — |
| A8: Plugins | High | 8-10 | A5, A3 | — |
| B1: Domain | Medium | 6-8 | A4 | — |
| B2: Repositories | Medium | 6-8 | A4, B1 | — |
| B3: WebSocket | Medium | 4-6 | A3 | — |
| B4: Queue | Medium | 6-8 | A4, A2 | — |
| B5: ProjectService | Medium | 4-6 | B2, A5 | — |
| B6: ImportService | Medium | 6-8 | B2, A5, A7, B4 | — |
| B7: SettingsService | Low | 2-3 | A2, B2 | — |
| B8: ProviderService | Medium | 4-6 | A8, B2, A2 | — |
| B9: PluginService | Low | 2-3 | A8 | — |
| B10: API Routes | Medium | 8-10 | B5-B9 | — |
| B11: App Factory | Medium | 4-6 | B10, B3, A3 | — |
| C1: STT Plugin | High | 8-10 | A8, A6 | — |
| C2: Vision Plugin | High | 6-8 | A8, A6 | — |
| C3: LLM Plugin | High | 8-10 | A8, A6 | — |
| C4: Pipeline | High | 10-12 | C1-C3, B4, B2 | C1-C3 |
| C5: AnalysisService | Medium | 4-6 | C4, B2 | C4 |
| C6: ClipGeneration | High | 8-10 | C4, C5, B2 | C4 |
| C7: CaptionService | Medium | 6-8 | C4, B2 | C4 |
| C8: ExportService | High | 8-10 | A7, A6, B2 | A7 |
| C9: AnalyticsService | Medium | 4-6 | C5, C6, B2 | C5, C6 |
| C10: API Routes | Medium | 6-8 | C4-C9, B11 | C4-C9 |
| D1: API Client | Medium | 6-8 | API contracts | C10 |
| D2: Project Browser | Medium | 4-6 | D1 | D1 |
| D3: Media Panel | Medium | 4-6 | D1 | D1 |
| D4: Video Preview | Medium | 4-6 | D1 | D1 |
| D5: Timeline Editor | Very High | 16-20 | D4, D1 | D4 |
| D6: Transcript Panel | Medium | 6-8 | D1 | D1 |
| D7: Clip Gallery | Medium | 4-6 | D1 | D1 |
| D8: Caption Editor | Medium | 6-8 | D1 | D1 |
| D9: Export Dialog | Low | 2-4 | D1 | D1 |
| D10: Settings UI | Medium | 8-10 | D1 | D1 |
| D11: Analytics UI | Medium | 4-6 | D1 | D1 |
| D12: Workspace | Medium | 6-8 | D2-D11 | D2-D11 |

**Total estimated effort:** ~250-300 hours of AI-assisted development

---

*End of Implementation Plan*
