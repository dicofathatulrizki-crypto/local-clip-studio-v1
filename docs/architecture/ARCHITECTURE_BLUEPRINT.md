# Local Clip Studio — Architecture Blueprint

> **Status:** DRAFT  
> **Version:** 1.0  
> **Date:** 2026-06-29  
> **Classification:** Engineering Blueprint — Single Source of Truth for Implementation  
> **Traceability:** Vision v2.0 → PRD v1.0 → SRS v1.0 → Blueprint v1.0

---

## Table of Contents

1. [System Context Diagram](#1-system-context-diagram)
2. [Component Architecture](#2-component-architecture)
3. [Module Decomposition](#3-module-decomposition)
4. [Dependency Graph](#4-dependency-graph)
5. [Data Flow Diagrams](#5-data-flow-diagrams)
6. [Deployment Architecture](#6-deployment-architecture)
7. [Runtime Architecture](#7-runtime-architecture)
8. [Plugin Architecture](#8-plugin-architecture)
9. [Hardware Abstraction Layer](#9-hardware-abstraction-layer)
10. [Cross-Cutting Concerns](#10-cross-cutting-concerns)
11. [Coding Standards](#11-coding-standards)
12. [Architecture Decision Records](#12-architecture-decision-records)
13. [Quality Gate Review](#13-quality-gate-review)

---

## 1. System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           LOCAL CLIP STUDIO SYSTEM CONTEXT                       │
│                                                                                  │
│  ┌──────────────┐                                                               │
│  │    User      │                                                               │
│  │  (Operator)  │──┐                                                           │
│  └──────────────┘  │  Keyboard/Mouse                                            │
│                    │  ┌─────────────────────────────────────────────────────┐    │
│                    ├──│                 BROWSER (localhost)                   │    │
│                    │  │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │    │
│                    │  │  │  UI Layer   │  │  Timeline    │  │  Preview   │ │    │
│                    └─▶│  │  (React SPA)│  │  (Canvas)    │  │  (Video)   │ │    │
│                       │  └──────┬──────┘  └──────────────┘  └────────────┘ │    │
│                       │         │HTTP REST + WebSocket                      │    │
│                       └─────────┼───────────────────────────────────────────┘    │
│                                 │                                                │
│  ┌──────────────────────────────┼────────────────────────────────────────────┐  │
│  │              FASTAPI SERVER (localhost:8765)                               │  │
│  │                                                                           │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐    │  │
│  │  │                     API Gateway Layer                             │    │  │
│  │  │  /api/v1/projects | /videos | /clips | /exports | /settings ...  │    │  │
│  │  └──────────────────────────────┬───────────────────────────────────┘    │  │
│  │                                 │                                        │  │
│  │  ┌──────────────────────────────┼───────────────────────────────────┐    │  │
│  │  │                    Application Service Layer                      │    │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │    │  │
│  │  │  │ Project  │ │ Import   │ │ Pipeline │ │ Export   │ │Settings│ │    │  │
│  │  │  │ Service  │ │ Service  │ │ Service  │ │ Service  │ │Service │ │    │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │    │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────────┐ │    │  │
│  │  │  │ Provider │ │ Plugin   │ │ Analytics│ │ Job Queue Manager   │ │    │  │
│  │  │  │ Service  │ │ Service  │ │ Service  │ │ (Celery Tasks)      │ │    │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └─────────────────────┘ │    │  │
│  │  └──────────────────────────────┬───────────────────────────────────┘    │  │
│  │                                 │                                        │  │
│  │  ┌──────────────────────────────┼───────────────────────────────────┐    │  │
│  │  │                     Domain Layer                                  │    │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │    │  │
│  │  │  │ Project  │ │ Video    │ │ Clip     │ │Transcript│ │Analysis│ │    │  │
│  │  │  │ Aggregate│ │ Entity   │ │ Entity   │ │ Value Obj│ │Entity  │ │    │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │    │  │
│  │  └──────────────────────────────┬───────────────────────────────────┘    │  │
│  │                                 │                                        │  │
│  │  ┌──────────────────────────────┼───────────────────────────────────┐    │  │
│  │  │                   Infrastructure Layer                             │    │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │    │  │
│  │  │  │ Database │ │ FileSys  │ │ HAL (GPU)│ │ FFmpeg   │ │ Queue  │ │    │  │
│  │  │  │ (SQLAlch)│ │ (fsspec) │ │ Abstrac. │ │ (Service)│ │(Celery)│ │    │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘ │    │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────────────────────────────┐ │    │  │
│  │  │  │ WebSocket│ │ Logger   │ │ Plugin Registry + Loader         │ │    │  │
│  │  │  │ Manager  │ │ (struct) │ │ (discovers & sandboxes plugins)  │ │    │  │
│  │  │  └──────────┘ └──────────┘ └──────────────────────────────────┘ │    │  │
│  │  └──────────────────────────────────────────────────────────────────┘    │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                 │                                              │
│     ┌───────────────────────────┼───────────────────────────┐                  │
│     │                           │                           │                  │
│     ▼                           ▼                           ▼                  │
│  ┌────────┐              ┌──────────────┐          ┌──────────────┐           │
│  │ SQLite │              │  File System  │          │  GPU Hardware │           │
│  │(local) │              │ ~/.localclip/ │          │  CUDA/MPS/CPU│           │
│  └────────┘              └──────────────┘          └──────────────┘           │
│                                                                                │
│     ┌──────────────┐     ┌──────────────┐     ┌─────────────────────┐         │
│     │   AI Models   │     │    FFmpeg     │     │ External AI APIs    │         │
│     │ (Whisper/YOLO │     │  (system)     │     │ (Opt: OpenAI, etc.) │         │
│     │  /Qwen/SAM)  │     │              │     │  via Internet)      │         │
│     └──────────────┘     └──────────────┘     └─────────────────────┘         │
│                                    (optional)                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 External System Boundaries

| System | Type | Communication | Optional |
|--------|------|---------------|----------|
| **SQLite** | Embedded DB | SQLAlchemy (file-based) | No |
| **File System** | Local storage | `pathlib`, fsspec | No |
| **GPU Hardware** | Hardware | PyTorch/ONNX via HAL | No |
| **FFmpeg** | System tool | Subprocess | No |
| **AI Models** | Local files | On-disk model files | No |
| **External AI APIs** | Internet service | HTTP (OpenAI, Anthropic, etc.) | Yes |
| **Browser** | UI runtime | HTTP REST + WebSocket | No |

---

## 2. Component Architecture

### 2.1 Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        UI LAYER (React SPA)                          │
│  Port: 5173 (dev) | Static files (prod)                             │
│  Communication: REST + WebSocket to FastAPI                         │
│  Container: Browser tab                                              │
├─────────────────────────────────────────────────────────────────────┤
│                     APPLICATION SERVICE LAYER                        │
│  FastAPI Application Server (Port: 8765)                            │
│  ├── API Gateway (routing, validation, request ID)                  │
│  ├── Services (Project, Import, Pipeline, Export, Provider, etc.)   │
│  ├── Job Queue (Celery tasks)                                       │
│  └── WebSocket Manager (event push)                                 │
├─────────────────────────────────────────────────────────────────────┤
│                         DOMAIN LAYER                                 │
│  Pure Python business logic                                         │
│  ├── Entities (Project, Video, Clip, Transcript, Analysis)          │
│  ├── Value Objects (QualityScore, TimeRange, BoundingBox)           │
│  ├── Aggregates (Project aggregate, Pipeline aggregate)             │
│  └── Domain Events (VideoImported, AnalysisCompleted, ExportDone)   │
├─────────────────────────────────────────────────────────────────────┤
│                       INFRASTRUCTURE LAYER                           │
│  ├── Database (SQLAlchemy repositories, Alembic migrations)         │
│  ├── FileSystem (path management, cleanup, permissions)             │
│  ├── HAL (GPU abstraction: CUDA/MPS/ROCm/CPU)                      │
│  ├── FFmpegService (wrapper subprocess commands)                    │
│  ├── WebSocket Management (connection pool, channels)               │
│  ├── Plugin System (discovery, loading, sandboxing)                 │
│  ├── Logging (structured JSON, rotation)                            │
│  └── Configuration (settings file, encryption)                      │
├─────────────────────────────────────────────────────────────────────┤
│                          AI LAYER                                     │
│  Plugin-based AI capabilities                                       │
│  ├── STT Provider Interface ← WhisperX, SenseVoice, OpenAI          │
│  ├── LLM Provider Interface ← Qwen, Llama, GPT, Claude              │
│  ├── Vision Provider Interface ← YOLO, SAM, OpenCV                  │
│  └── Pipeline Orchestrator (stages, caching, progress)              │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibilities | Dependencies |
|-----------|-----------------|--------------|
| **API Gateway** | Route requests, validate input, assign request IDs, format errors | Service layer |
| **ProjectService** | CRUD projects, recent projects, version history, backup/restore | ProjectRepository, FileSystemService |
| **ImportService** | Validate files, hash dedup, copy to storage, extract metadata, generate proxy | VideoMasterRepo, ProjectVideoRepo, FFmpegService |
| **PipelineService** | Orchestrate AI pipeline, manage stage execution, caching, progress reporting | All plugins, AnalysisRepo, JobQueue, HAL |
| **ExportService** | Build FFmpeg commands, select GPU encoder, monitor progress | FFmpegService, HAL, ExportJobRepo |
| **ProviderService** | Manage provider configs, test connections, route tasks, fallback chains | PluginRegistry, SettingsService |
| **PluginService** | Discover, load, validate, sandbox plugins | FileSystem, PluginRegistry |
| **SettingsService** | Read/write config, validate, encrypt/decrypt API keys | SettingsRepository |
| **AnalyticsService** | Calculate quality scores, virality, engagement metrics | AnalysisRepo |
| **WebSocketManager** | Manage connections, channel subscriptions, push events | — |
| **FFmpegService** | Execute FFmpeg commands, probe files, parse progress | Subprocess, FileSystem |
| **HALRegistry** | Detect backends, select best, manage memory | PyTorch |
| **JobQueue** | Enqueue/dequeue jobs, manage workers, persistence | Celery, Redis/FileSystem |
| **Logger** | Structured JSON logging, rotation, correlation IDs | FileSystem |

---

## 3. Module Decomposition

### 3.1 Complete Package Structure

```
local-clip-studio/
│
├── frontend/                          # React SPA
│   ├── public/                        # Static assets
│   ├── src/
│   │   ├── components/                # React components
│   │   │   ├── workspace/             # Main workspace layout
│   │   │   │   ├── Workspace.tsx      # Root workspace container
│   │   │   │   ├── Panel.tsx          # Dockable panel wrapper
│   │   │   │   └── StatusBar.tsx      # Status bar
│   │   │   ├── project/               # Project management
│   │   │   │   ├── ProjectBrowser.tsx  # Project list grid
│   │   │   │   └── ProjectSettings.tsx # Project configuration
│   │   │   ├── timeline/              # Timeline editor
│   │   │   │   ├── Timeline.tsx        # Main timeline component
│   │   │   │   ├── TimelineTrack.tsx   # Single track
│   │   │   │   ├── TimelineClip.tsx    # Clip on track
│   │   │   │   ├── Waveform.tsx        # Audio waveform rendering
│   │   │   │   ├── TimeRuler.tsx       # Time axis
│   │   │   │   └── Playhead.tsx        # Current position cursor
│   │   │   ├── preview/               # Video preview
│   │   │   │   ├── Preview.tsx         # Video player
│   │   │   │   └── CaptionOverlay.tsx  # Caption rendering
│   │   │   ├── media/                 # Media management
│   │   │   │   ├── MediaBrowser.tsx   # Media files panel
│   │   │   │   └── ImportDialog.tsx   # Import video dialog
│   │   │   ├── transcript/            # Transcript panel
│   │   │   │   ├── TranscriptPanel.tsx # Full transcript view
│   │   │   │   ├── TranscriptSegment.tsx # Single segment
│   │   │   │   └── SearchTranscript.tsx# Search in transcript
│   │   │   ├── clips/                 # Clip management
│   │   │   │   ├── ClipGallery.tsx    # Ranked clip grid
│   │   │   │   └── ClipCard.tsx       # Single clip preview
│   │   │   ├── captions/              # Caption editor
│   │   │   │   ├── CaptionEditor.tsx
│   │   │   │   ├── StylePresets.tsx
│   │   │   │   └── FontPicker.tsx
│   │   │   ├── settings/              # Settings panels
│   │   │   │   ├── SettingsDialog.tsx
│   │   │   │   ├── GeneralSettings.tsx
│   │   │   │   ├── Appearance.tsx
│   │   │   │   ├── Storage.tsx
│   │   │   │   ├── GPU.tsx
│   │   │   │   ├── AIProviders.tsx
│   │   │   │   ├── APIKeys.tsx
│   │   │   │   ├── ExportSettings.tsx
│   │   │   │   └── KeyboardShortcuts.tsx
│   │   │   ├── export/                # Export dialog
│   │   │   │   └── ExportDialog.tsx
│   │   │   ├── analytics/             # Processing analytics
│   │   │   │   ├── QualityScore.tsx
│   │   │   │   ├── ViralityGraph.tsx
│   │   │   │   └── EmotionTimeline.tsx
│   │   │   └── common/                # Reusable UI
│   │   │       ├── ProgressBar.tsx
│   │   │       ├── LoadingSpinner.tsx
│   │   │       └── ErrorBoundary.tsx
│   │   ├── hooks/                     # Custom React hooks
│   │   │   ├── useTimeline.ts
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useProject.ts
│   │   │   ├── useImport.ts
│   │   │   ├── useAnalysis.ts
│   │   │   ├── useExport.ts
│   │   │   └── useKeyboard.ts
│   │   ├── store/                     # Zustand stores
│   │   │   ├── useProjectStore.ts
│   │   │   ├── useTimelineStore.ts
│   │   │   ├── usePlayerStore.ts
│   │   │   └── useSettingsStore.ts
│   │   ├── api/                       # API client
│   │   │   ├── client.ts              # Axios/fetch wrapper
│   │   │   ├── projects.ts
│   │   │   ├── videos.ts
│   │   │   ├── clips.ts
│   │   │   ├── exports.ts
│   │   │   ├── providers.ts
│   │   │   ├── settings.ts
│   │   │   └── websocket.ts
│   │   ├── lib/                       # Utilities
│   │   │   ├── utils.ts
│   │   │   ├── format.ts              # Time/date formatting
│   │   │   ├── keyboard.ts            # Shortcut definitions
│   │   │   └── theme.ts               # Theme tokens
│   │   ├── types/                     # TypeScript types
│   │   │   ├── project.ts
│   │   │   ├── video.ts
│   │   │   ├── clip.ts
│   │   │   ├── transcript.ts
│   │   │   ├── timeline.ts
│   │   │   ├── export.ts
│   │   │   ├── provider.ts
│   │   │   └── settings.ts
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── package.json
│
├── backend/                           # Python FastAPI
│   ├── api/                           # API Gateway Layer
│   │   ├── __init__.py
│   │   ├── app.py                     # FastAPI application factory
│   │   ├── middleware.py              # CORS, request ID, error handler
│   │   ├── deps.py                    # Dependency injection
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── projects.py
│   │   │   ├── videos.py
│   │   │   ├── clips.py
│   │   │   ├── timeline.py
│   │   │   ├── exports.py
│   │   │   ├── providers.py
│   │   │   ├── settings.py
│   │   │   ├── system.py
│   │   │   └── models.py              # Model download endpoints
│   │   └── websocket/
│   │       ├── __init__.py
│   │       ├── manager.py             # Connection manager
│   │       └── handlers.py            # Event handlers
│   │
│   ├── services/                      # Application Service Layer
│   │   ├── __init__.py
│   │   ├── project_service.py
│   │   ├── import_service.py
│   │   ├── pipeline_service.py
│   │   ├── export_service.py
│   │   ├── provider_service.py
│   │   ├── plugin_service.py
│   │   ├── settings_service.py
│   │   └── analytics_service.py
│   │
│   ├── domain/                        # Domain Layer
│   │   ├── __init__.py
│   │   ├── entities/
│   │   │   ├── __init__.py
│   │   │   ├── project.py
│   │   │   ├── video.py
│   │   │   ├── clip.py
│   │   │   ├── transcript.py
│   │   │   └── analysis.py
│   │   ├── value_objects/
│   │   │   ├── __init__.py
│   │   │   ├── time_range.py
│   │   │   ├── quality_score.py
│   │   │   ├── bounding_box.py
│   │   │   └── transcript_segment.py
│   │   ├── aggregates/
│   │   │   ├── __init__.py
│   │   │   └── project_aggregate.py
│   │   └── events/
│   │       ├── __init__.py
│   │       ├── video_imported.py
│   │       ├── analysis_completed.py
│   │       └── export_completed.py
│   │
│   ├── infrastructure/               # Infrastructure Layer
│   │   ├── __init__.py
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py              # DB engine + session factory
│   │   │   ├── models/                # SQLAlchemy ORM models
│   │   │   │   ├── __init__.py
│   │   │   │   ├── project.py
│   │   │   │   ├── video_master.py
│   │   │   │   ├── project_video.py
│   │   │   │   ├── analysis.py
│   │   │   │   ├── clip_candidate.py
│   │   │   │   ├── timeline_state.py
│   │   │   │   ├── export_job.py
│   │   │   │   ├── processing_queue.py
│   │   │   │   └── caption_track.py
│   │   │   ├── repositories/          # Repository implementations
│   │   │   │   ├── __init__.py
│   │   │   │   ├── project_repo.py
│   │   │   │   ├── video_master_repo.py
│   │   │   │   ├── analysis_repo.py
│   │   │   │   ├── clip_repo.py
│   │   │   │   ├── export_job_repo.py
│   │   │   │   └── settings_repo.py
│   │   │   └── migrations/            # Alembic
│   │   │       ├── env.py
│   │   │       ├── alembic.ini
│   │   │       └── versions/
│   │   ├── filesystem/
│   │   │   ├── __init__.py
│   │   │   ├── project_dirs.py        # Project directory management
│   │   │   ├── storage_manager.py     # Cleanup, limits, usage tracking
│   │   │   └── file_ops.py            # Copy, move, hash, permissions
│   │   ├── hal/                       # Hardware Abstraction Layer
│   │   │   ├── __init__.py
│   │   │   ├── interface.py           # HALProvider ABC
│   │   │   ├── registry.py            # HALRegistry singleton
│   │   │   ├── backends/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── cuda_provider.py
│   │   │   │   ├── mps_provider.py
│   │   │   │   ├── rocm_provider.py
│   │   │   │   └── cpu_provider.py
│   │   │   └── memory_manager.py      # VRAM budgeting
│   │   ├── ffmpeg/
│   │   │   ├── __init__.py
│   │   │   ├── ffmpeg_service.py      # Command construction + execution
│   │   │   ├── ffprobe_service.py     # Metadata extraction
│   │   │   ├── commands.py            # Command templates
│   │   │   └── progress_parser.py     # Parse FFmpeg stderr for progress
│   │   ├── queue/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py          # Celery configuration
│   │   │   ├── tasks/                 # Celery task definitions
│   │   │   │   ├── __init__.py
│   │   │   │   ├── analysis.py
│   │   │   │   ├── export.py
│   │   │   │   ├── import_video.py
│   │   │   │   └── model_download.py
│   │   │   └── worker.py              # Worker lifecycle
│   │   ├── plugins/
│   │   │   ├── __init__.py
│   │   │   ├── registry.py            # Plugin discovery + registration
│   │   │   ├── loader.py              # Plugin loading + sandboxing
│   │   │   ├── interfaces/            # Plugin interface definitions
│   │   │   │   ├── __init__.py
│   │   │   │   ├── stt_provider.py
│   │   │   │   ├── llm_provider.py
│   │   │   │   ├── vision_provider.py
│   │   │   │   ├── caption_provider.py
│   │   │   │   ├── translation_provider.py
│   │   │   │   └── export_provider.py
│   │   │   └── builtins/              # Built-in plugin implementations
│   │   │       ├── __init__.py
│   │   │       ├── whisperx_stt.py
│   │   │       ├── llama_llm.py
│   │   │       ├── yolo_vision.py
│   │   │       └── pyscenedetect_scene.py
│   │   ├── websocket/
│   │   │   ├── __init__.py
│   │   │   └── manager.py
│   │   └── logging/
│   │       ├── __init__.py
│   │       ├── logger.py              # Structured JSON logger
│   │       └── correlation.py         # Request ID propagation
│   │
│   ├── config/                        # Configuration
│   │   ├── __init__.py
│   │   ├── settings.py                # Pydantic settings model
│   │   ├── defaults.py                # Default configuration values
│   │   └── encryption.py              # Fernet key management
│   │
│   └── main.py                        # Application entry point
│
├── plugins/                           # User-installed plugins directory
│   └── (dynamically populated)
│
├── models/                            # AI model download scripts
│   ├── download.py                    # Model download manager
│   └── registry.json                  # Model catalog
│
├── scripts/                           # Utility scripts
│   ├── setup.sh                       # Environment setup
│   ├── install_ffmpeg.sh
│   ├── download_models.sh
│   └── dev.sh                         # Start development servers
│
├── tests/                             # Test suite
│   ├── __init__.py
│   ├── conftest.py                    # Shared fixtures
│   ├── unit/
│   │   ├── services/
│   │   ├── domain/
│   │   ├── hal/
│   │   └── pipeline/
│   ├── integration/
│   │   ├── test_project_api.py
│   │   ├── test_import_api.py
│   │   └── test_export_api.py
│   ├── e2e/
│   │   └── test_workflows.py
│   ├── performance/
│   │   └── test_pipeline_benchmarks.py
│   └── fixtures/
│       ├── sample_video_10s.mp4
│       └── sample_audio.wav
│
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── .dockerignore
│
├── docs/                              # Documentation
│   ├── vision/VISION_DOCUMENT.md
│   ├── PRD.md
│   ├── SRS.md
│   └── architecture/
│       ├── ARCHITECTURE_BLUEPRINT.md
│       └── adr/
│           ├── INDEX.md
│           ├── ADR-001-react-frontend.md
│           ├── ADR-002-fastapi-backend.md
│           ├── ADR-003-sqlite.md
│           ├── ADR-004-sqlalchemy.md
│           ├── ADR-005-rest-api.md
│           ├── ADR-006-websocket.md
│           ├── ADR-007-plugin-system.md
│           ├── ADR-008-hardware-abstraction.md
│           ├── ADR-009-local-first.md
│           ├── ADR-010-storage-layout.md
│           ├── ADR-011-ai-provider-abstraction.md
│           ├── ADR-012-background-job-queue.md
│           ├── ADR-013-ffmpeg-integration.md
│           ├── ADR-014-no-authentication.md
│           ├── ADR-015-domain-driven-design.md
│           └── ADR-016-cqrs-pattern.md
│
├── pyproject.toml                     # Python dependencies
├── requirements.txt
├── Makefile
├── README.md
└── .env.example
```

### 3.2 Module Responsibility Matrix

| Module | Purpose | Public Interface | Dependencies |
|--------|---------|-----------------|--------------|
| `backend/api/` | HTTP + WebSocket entry point | Route handlers, middleware | All services |
| `backend/services/` | Business logic orchestration | Service classes | Domain + Infrastructure |
| `backend/domain/` | Pure business logic (no I/O) | Entities, Value Objects, Events | None |
| `backend/infrastructure/database/` | Data persistence | Repository interfaces + implementations | SQLAlchemy |
| `backend/infrastructure/hal/` | GPU abstraction | HALProvider + HALRegistry | PyTorch |
| `backend/infrastructure/ffmpeg/` | Video processing | FFmpegService | Subprocess |
| `backend/infrastructure/plugins/` | Plugin lifecycle | PluginRegistry, interfaces | Importlib |
| `backend/infrastructure/queue/` | Background jobs | Celery tasks | Celery |
| `backend/infrastructure/filesystem/` | File management | StorageManager | pathlib |
| `backend/infrastructure/websocket/` | Event streaming | WebSocketManager | FastAPI WebSocket |
| `backend/infrastructure/logging/` | Structured logging | Logger | structlog |
| `frontend/src/` | User interface | React components | API client |

---

## 4. Dependency Graph

### 4.1 Layer Dependency Rules

```
┌──────────────┐
│  UI Layer    │────→ HTTP REST + WebSocket ────→┐
│  (React SPA) │                                  │
└──────────────┘                                  ▼
                                          ┌──────────────┐
                                          │ API Gateway   │
                                          └──────┬───────┘
                                                 │
                                                 ▼
                                          ┌──────────────┐
                                          │ Service Layer │
                                          └──────┬───────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    │                            │                            │
                    ▼                            ▼                            ▼
            ┌──────────────┐            ┌──────────────┐            ┌──────────────┐
            │  Domain Layer│◀───────────│  AI Layer     │            │ Plugin Layer │
            │  (Pure Logic)│            │  (Plugins)    │            │  (Registry)  │
            └──────────────┘            └──────────────┘            └──────┬───────┘
                    ▲                                                      │
                    │                                                      │
                    └──────────────────────┬───────────────────────────────┘
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │Infrastructure │
                                    │   Layer       │
                                    │───────────────│
                                    │ • Database     │
                                    │ • FileSystem   │
                                    │ • HAL (GPU)    │
                                    │ • FFmpeg       │
                                    │ • Queue        │
                                    │ • Logging      │
                                    └────────────────┘
```

### 4.2 Strict Dependency Rules

```
RULE 1: Domain → (nothing)
  Domain entities must have zero dependencies on frameworks, databases, or infrastructure.

RULE 2: Service → Domain, Infrastructure
  Services import domain entities and infrastructure interfaces (not implementations).

RULE 3: Infrastructure → Domain
  Infrastructure implements domain-defined repository interfaces.
  Infrastructure never depends on services.

RULE 4: AI Layer → Plugin interfaces (only)
  No AI module may directly import whisperx, torch, or any concrete provider.

RULE 5: Plugin Layer → Infrastructure interfaces
  Plugins implement interfaces from infrastructure/plugins/interfaces/.
  Plugins may use HAL for GPU access (through HAL interface, never directly).

RULE 6: API → Service
  Route handlers call service methods. They never access repositories directly.

RULE 7: UI → API only
  Frontend communicates only through HTTP REST and WebSocket.

RULE 8: No circular dependencies (enforced by import linter)
```

### 4.3 Forbidden Dependencies

| From | To | Reason |
|------|----|--------|
| Domain | Infrastructure | Domain must not know about databases |
| Domain | Service | Domain is a lower layer |
| Infrastructure | Service | Would create circular dependency |
| Service | UI | Backend must not depend on frontend |
| Plugin | Domain directly | Plugin should use domain objects only through service contracts |
| Service | Concrete AI model | Must go through plugin interface |

---

## 5. Data Flow Diagrams

### 5.1 Import Video Flow

```
User                          Browser                    FastAPI                    FileSystem/DB
 │                              │                          │                          │
 │ 1. Select file (drag/click)  │                          │                          │
 │─────────────────────────────▶│                          │                          │
 │                              │                          │                          │
 │                              │ 2. POST /videos          │                          │
 │                              │    (multipart form-data) │                          │
 │                              │─────────────────────────▶│                          │
 │                              │                          │                          │
 │                              │                          │ 3. Validate extension     │
 │                              │                          │ 4. Check size limit       │
 │                              │                          │ 5. FFprobe probe file     │
 │                              │                          │ 6. Compute SHA-256        │
 │                              │                          │ 7. Check duplicate        │
 │                              │                          │──────────────────────────▶│
 │                              │                          │                          │
 │                              │                          │ 8. Copy to sources/ dir   │
 │                              │                          │ 9. Create ProjectVideo    │
 │                              │                          │ 10. Generate proxy video  │
 │                              │                          │ (async via queue)         │
 │                              │                          │──────────────────────────▶│
 │                              │                          │                          │
 │                              │ 11. 201 Created          │                          │
 │                              │     (video metadata)     │                          │
 │                              │◀─────────────────────────│                          │
 │                              │                          │                          │
 │ 12. Show video in Media Panel│                          │                          │
 │◀─────────────────────────────│                          │                          │
 │                              │                          │                          │
 │                              │ 13. WebSocket: job.progress (proxy generation)       │
 │                              │◀────────────────────────────────────────────────────│
 │                              │                          │                          │
 │ 14. Show "Ready" status     │                          │                          │
 │◀─────────────────────────────│                          │                          │
```

### 5.2 AI Analysis Flow

```
User          Browser              FastAPI                Worker/Plugin              FileSystem/DB
 │               │                    │                        │                        │
 │ 1. Click "Analyze"                │                        │                        │
 │──────────────▶│                    │                        │                        │
 │               │ 2. POST /analyze   │                        │                        │
 │               │───────────────────▶│                        │                        │
 │               │                    │ 3. Create job (QUEUED) │                        │
 │               │                    │───────────────────────────────────────────────▶│
 │               │                    │ 4. Enqueue Celery task│                        │
 │               │                    │──────────────────────▶│                        │
 │               │                    │                        │                        │
 │               │ 5. 202 Accepted    │                        │                        │
 │               │◀───────────────────│                        │                        │
 │               │                    │                        │                        │
 │               │ 6. WS: job.progress│                        │                        │
 │               │◀───────────────────│                        │                        │
 │               │                    │ 7. Stage: Preprocessing│                        │
 │               │                    │◀───────────────────────│                        │
 │               │                    │ 8. Extract audio       │                        │
 │               │                    │ 9. Extract frames      │───────────────────────▶│
 │               │                    │ 10. Generate proxy     │                        │
 │               │                    │                        │                        │
 │               │ 11. WS: pipeline.stage (transcribing)      │                        │
 │               │◀───────────────────│                        │                        │
 │               │                    │ 12. STT Plugin::transcribe(audio)               │
 │               │                    │◀───────────────────────│                        │
 │               │                    │ 13. Return transcript  │                        │
 │               │                    │───────────────────────▶│                        │
 │               │                    │                        │                        │
 │               │ 14. WS: pipeline.stage (scene_detecting)   │                        │
 │               │◀───────────────────│                        │                        │
 │               │                    │ 15. SceneDetect::detect(frames)                 │
 │               │                    │◀───────────────────────│                        │
 │               │                    │                        │                        │
 │               │ 16. WS: pipeline.stage (analyzing)         │                        │
 │               │◀───────────────────│                        │                        │
 │               │                    │ 17. LLM Plugin::analyze(transcript, scenes)     │
 │               │                    │◀───────────────────────│                        │
 │               │                    │                        │                        │
 │               │ 18. WS: pipeline.stage (scoring)           │                        │
 │               │◀───────────────────│                        │                        │
 │               │                    │ 19. Calculate quality score                      │
 │               │                    │ 20. Save analysis to DB │                        │
 │               │                    │───────────────────────────────────────────────▶│
 │               │                    │                        │                        │
 │               │ 21. WS: job.completed                     │                        │
 │               │◀───────────────────│                        │                        │
 │               │                    │                        │                        │
 │ 22. Show transcript + scenes     │                        │                        │
 │◀──────────────│                    │                        │                        │
```

### 5.3 Clip Generation Flow

```
User          Browser              FastAPI                Worker (PipelineService)
 │               │                    │                        │
 │ 1. Click "Generate Clips"         │                        │
 │──────────────▶│                    │                        │
 │               │ 2. POST /clips/generate                    │
 │               │───────────────────▶│                        │
 │               │                    │ 3. Load analysis data  │
 │               │                    │───────────────────────▶│
 │               │                    │                        │
 │               │                    │ 4. Extract candidates: │
 │               │                    │    - High-hook moments │
 │               │                    │    - Scene boundaries  │
 │               │                    │    - Score thresholds  │
 │               │                    │                        │
 │               │                    │ 5. For each candidate: │
 │               │                    │    - Trim silence      │
 │               │                    │    - Calculate score   │
 │               │                    │    - Rank              │
 │               │                    │                        │
 │               │                    │ 6. Deduplicate        │
 │               │                    │ 7. Merge overlapping   │
 │               │                    │                        │
 │               │                    │ 8. LLM: Generate       │
 │               │                    │    title, desc, tags   │
 │               │                    │───────────────────────▶│
 │               │                    │ 9. Return clips        │
 │               │◀───────────────────│                        │
 │               │                    │                        │
 │ 10. Show ranked clip gallery     │                        │
 │◀──────────────│                    │                        │
```

### 5.4 Export Flow

```
User          Browser              FastAPI                FFmpeg Subprocess        FileSystem
 │               │                    │                        │                    │
 │ 1. Click "Export"                 │                        │                    │
 │──────────────▶│                    │                        │                    │
 │               │ 2. ExportDialog    │                        │                    │
 │               │ 3. User selects   │                        │                    │
 │               │    format, preset  │                        │                    │
 │               │                    │                        │                    │
 │               │ 4. POST /exports   │                        │                    │
 │               │───────────────────▶│                        │                    │
 │               │                    │ 5. Create ExportJob    │                    │
 │               │                    │ 6. Select GPU encoder  │                    │
 │               │                    │ 7. Build FFmpeg cmd    │                    │
 │               │                    │───────────────────────▶│                    │
 │               │                    │                        │                    │
 │               │                    │ 8. spawn ffmpeg        │                    │
 │               │                    │───────────────────────▶│                    │
 │               │                    │                        │ 9. Encode video    │
 │               │                    │                        │ 10. Overlay caps   │
 │               │                    │                        │ 11. Apply reframe  │
 │               │                    │                        │ 12. Write file     │
 │               │                    │                        │───────────────────▶│
 │               │                    │                        │                    │
 │               │ 13. WS: export.progress (per frame)         │                    │
 │               │◀────────────────────────────────────────────│                    │
 │               │                    │                        │                    │
 │               │                    │ 14. FFmpeg exit code 0 │                    │
 │               │                    │◀───────────────────────│                    │
 │               │                    │ 15. Update job status  │                    │
 │               │ 16. WS: job.completed                      │                    │
 │               │◀───────────────────│                        │                    │
 │               │                    │                        │                    │
 │ 17. Show "Export Complete"        │                        │                    │
 │◀──────────────│                    │                        │                    │
```

### 5.5 Timeline Editing Flow

```
User          Browser (React)         Zustand Store           FastAPI (save)
 │               │                        │                      │
 │ 1. Drag clip on timeline             │                      │
 │──────────────▶│                        │                      │
 │               │ 2. Update local state  │                      │
 │               │───────────────────────▶│                      │
 │               │                        │ 3. Optimistic update │
 │               │                        │ 4. Re-render         │
 │               │◀───────────────────────│                      │
 │               │                        │                      │
 │               │ 5. Debounce (1s)       │                      │
 │               │                        │ 6. PUT /timeline     │
 │               │                        │─────────────────────▶│
 │               │                        │                      │
 │               │                        │ 7. Save to DB        │
 │               │                        │ 8. Return new version│
 │               │                        │◀─────────────────────│
 │               │                        │                      │
 │               │ 9. Confirm optimistic  │                      │
 │               │◀───────────────────────│                      │
```

### 5.6 Plugin Loading Flow

```
FastAPI Startup                     Plugin Directory            Plugin Registry
     │                                    │                          │
     │ 1. Scan plugins/ directory         │                          │
     │───────────────────────────────────▶│                          │
     │                                    │                          │
     │ 2. List plugin subdirectories      │                          │
     │◀───────────────────────────────────│                          │
     │                                    │                          │
     │ 3. For each plugin:                │                          │
     │    a. Read manifest.json           │                          │
     │    b. Validate manifest schema     │                          │
     │    c. Check app version compat     │                          │
     │    d. Check Python dependencies    │                          │
     │    e. Check model availability     │                          │
     │    f. Import entry_point module    │                          │
     │    g. Instantiate plugin class     │                          │
     │    h. Call plugin.load()           │                          │
     │    i. Register in registry         │                          │
     │─────────────────────────────────────────────────────────────▶│
     │                                    │                          │
     │ 4. Registry ready                  │                          │
     │◀───────────────────────────────────│                          │
     │                                    │                          │
     │ 5. Mark plugin as ACTIVE           │                          │
     │ 6. Schedule periodic health checks │                          │
```

### 5.7 Model Download Flow

```
User          Browser              FastAPI              Download Worker        HuggingFace/URL
 │               │                    │                      │                    │
 │ 1. Settings → AI Models           │                      │                    │
 │    Click "Download"                │                      │                    │
 │──────────────▶│                    │                      │                    │
 │               │ 2. POST /models/download                │                    │
 │               │    {model_id, size_mb}                  │                    │
 │               │───────────────────▶│                      │                    │
 │               │                    │ 3. Create download job                   │
 │               │                    │ 4. Check disk space  │                    │
 │               │                    │ 5. Enqueue task      │                    │
 │               │                    │─────────────────────▶│                    │
 │               │                    │                      │                    │
 │               │ 6. 202 Accepted    │                      │                    │
 │               │◀───────────────────│                      │                    │
 │               │                    │                      │                    │
 │               │ 7. WS: model.download (progress)         │                    │
 │               │◀─────────────────────────────────────────│                    │
 │               │                    │ 8. Download model    │                    │
 │               │                    │    (streaming)       │───────────────────▶│
 │               │                    │                      │◀───────────────────│
 │               │                    │                      │                    │
 │               │                    │ 9. Verify checksum   │                    │
 │               │                    │ 10. Move to models/  │                    │
 │               │                    │─────────────────────▶│                    │
 │               │                    │                      │                    │
 │               │ 11. WS: job.completed                    │                    │
 │               │◀───────────────────│                      │                    │
 │               │                    │                      │                    │
 │ 12. Show "Ready" in model list    │                      │                    │
 │◀──────────────│                    │                      │                    │
```

---

## 6. Deployment Architecture

### 6.1 Localhost Deployment

```
┌──────────────────────────────────────────────────────────────┐
│                    SINGLE MACHINE DEPLOYMENT                   │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Frontend (Vite Dev Server / Static Files)              │  │
│  │  Port: 5173 (dev) / served by FastAPI (prod)           │  │
│  │  Process: Node.js (dev) / Static (prod)                │  │
│  └──────────────────────┬─────────────────────────────────┘  │
│                         │ HTTP REST + WebSocket              │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  FastAPI Server (uvicorn)                               │  │
│  │  Port: 8765                                            │  │
│  │  Process: 1 main process + N workers                   │  │
│  │  Start: python -m backend.main                         │  │
│  └──────────────────────┬─────────────────────────────────┘  │
│                         │                                    │
│         ┌───────────────┼───────────────┐                    │
│         │               │               │                    │
│         ▼               ▼               ▼                    │
│  ┌──────────┐   ┌────────────┐   ┌──────────────┐          │
│  │ SQLite   │   │ FileSystem │   │ Celery Worker │          │
│  │ (file)   │   │~/.localclip│   │ (background)  │          │
│  └──────────┘   └────────────┘   └──────┬───────┘          │
│                                         │                    │
│                                         ▼                    │
│                                  ┌──────────────┐           │
│                                  │  GPU (CUDA)  │           │
│                                  │  / MPS / CPU │           │
│                                  └──────────────┘           │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 Docker Deployment

```yaml
# docker-compose.yml
services:
  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8765:8765"
    volumes:
      - localclip_data:/home/user/.localclip
      - /path/to/models:/home/user/.localclip/models
    environment:
      - LOCALCLIP_STORAGE_PATH=/home/user/.localclip
      - LOCALCLIP_GPU_BACKEND=auto
    devices:
      - /dev/nvidia0:/dev/nvidia0  # If NVIDIA GPU
      - /dev/dri:/dev/dri           # If AMD GPU
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
    restart: unless-stopped

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile
    command: celery -A backend.infrastructure.queue.celery_app worker --loglevel=info
    volumes:
      - localclip_data:/home/user/.localclip
      - /path/to/models:/home/user/.localclip/models
    environment:
      - LOCALCLIP_STORAGE_PATH=/home/user/.localclip
      - LOCALCLIP_GPU_BACKEND=auto
      - CELERY_BROKER_URL=filesystem://
    devices:
      - /dev/nvidia0:/dev/nvidia0
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
    restart: unless-stopped

volumes:
  localclip_data:
```

### 6.3 Startup Sequence

```
1. System Prerequisites Check
   ├── Python 3.11+ available
   ├── FFmpeg 6.0+ available (ffmpeg -version)
   ├── PyTorch installed with GPU support (optional)
   └── ~/.localclip/ directory created

2. Backend Startup (FastAPI)
   ├── Load configuration (settings.json)
   ├── Initialize database (create tables if needed)
   ├── Run pending Alembic migrations
   ├── Initialize HAL (detect GPU backends)
   ├── Initialize plugin registry (scan plugins/)
   ├── Initialize Celery worker pool
   ├── Initialize WebSocket manager
   └── Start uvicorn server on port 8765

3. Frontend Startup (Vite)
   ├── Install dependencies (npm install)
   ├── Start Vite dev server on port 5173
   └── Open browser to http://localhost:5173

4. Application Ready
   └── Browser connects to FastAPI via REST + WebSocket
```

### 6.4 Port Map

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| FastAPI | 8765 | HTTP | REST API |
| FastAPI | 8765 | WebSocket | Real-time events |
| Vite (dev) | 5173 | HTTP | Frontend dev server |
| Docker (Redis) | 6379 | TCP | Optional Celery broker |

---

## 7. Runtime Architecture

### 7.1 Background Job Queue

```
┌──────────────────────────────────────────────────────────────┐
│                     CELERY TASK QUEUE                          │
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │  Producer     │───▶│   Broker     │───▶│   Worker     │    │
│  │  (FastAPI)    │    │ (Filesystem/ │    │  (Subprocess) │    │
│  │               │    │   Redis)     │    │              │    │
│  └──────────────┘    └──────────────┘    └──────┬───────┘    │
│                                                  │            │
│                                                  ▼            │
│                                         ┌──────────────┐     │
│                                         │  Result Backend │    │
│                                         │  (SQLite DB)   │    │
│                                         └──────────────┘     │
│                                                               │
│  Task Types:                                                  │
│  ┌─────────────────────┬────────────┬────────────────────────┐│
│  │ Task                │ Queue      │ Worker Type            ││
│  ├─────────────────────┼────────────┼────────────────────────┤│
│  │ import_video        │ import     │ I/O bound (CPU-light)  ││
│  │ run_pipeline        │ pipeline   │ GPU-bound (model inf)  ││
│  │ export_video        │ export     │ GPU-bound (encoding)   ││
│  │ download_model      │ download   │ Network-bound          ││
│  │ generate_clips      │ analysis   │ CPU-bound (scoring)    ││
│  │ cleanup_storage     │ maintenance│ I/O bound              ││
│  └─────────────────────┴────────────┴────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

### 7.2 Worker Lifecycle

```
┌──────────────┐
│  Worker Pool  │
│  (4 processes)│
├──────────────┤
│ Worker 0      │─── GPU slot 0 (pipeline, export)
│ Worker 1      │─── GPU slot 1 (pipeline, export)
│ Worker 2      │─── CPU-only (import, cleanup)
│ Worker 3      │─── CPU-only (download, analysis)
└──────────────┘
     │
     ▼
┌────────────────┐
│ Worker States  │
├────────────────┤
│ IDLE           │── Waiting for work
│ RESERVED       │── Task assigned, starting
│ ACTIVE         │── Executing task
│ SUSPENDED      │── Waiting for resource (GPU)
│ COMPLETED      │── Task done
│ FAILED         │── Task error
│ SHUTDOWN       │── Worker terminating
└────────────────┘
```

### 7.3 WebSocket Communication

```
┌──────────────┐                    ┌──────────────┐
│  Frontend     │                    │  Backend     │
│  (Browser)   │                    │  (FastAPI)   │
├──────────────┤                    ├──────────────┤
│ WS Client    │◀───────────────────▶│ WS Manager   │
│              │   Event Stream     │              │
│              │                    │  ┌────────┐  │
│              │                    │  │ Channel │  │
│              │                    │  │  Map    │  │
│              │                    │  └────────┘  │
└──────────────┘                    └──────┬───────┘
                                          │
                                          ▼
                                  ┌──────────────┐
                                  │  Event Bus    │
                                  │  (in-process) │
                                  ├──────────────┤
                                  │ job.progress  │
                                  │ job.completed │
                                  │ job.failed    │
                                  │ export.prog.  │
                                  │ model.download│
                                  │ system.warn   │
                                  └──────────────┘
```

### 7.4 Threading Model

| Component | Threading | Rationale |
|-----------|-----------|-----------|
| **FastAPI (uvicorn)** | Async (asyncio event loop) | I/O-bound request handling |
| **Celery Worker** | Multi-process (prefork) | CPU/GPU-bound pipeline tasks |
| **FFmpeg Subprocess** | Separate process | Long-running video encoding |
| **HAL (GPU)** | Main thread + CUDA streams | GPU operations are async within PyTorch |
| **Plugin Execution** | Thread pool | Plugin isolation from main event loop |
| **File Operations** | Async (aiofiles) | Non-blocking file I/O |
| **Logging** | Background thread | Queue-based log emission |

### 7.5 Caching Strategy

| Cache | Location | Key | TTL | Size Limit |
|-------|----------|-----|-----|------------|
| Analysis results | `cache/analysis/` | `{video_hash}_analysis.json` | Until video removed | 500 MB |
| Audio extraction | `cache/audio/` | `{video_hash}_16khz.wav` | 7 days | 5 GB |
| Frame extraction | `cache/frames/` | `{video_hash}_frames/` | 7 days | 10 GB |
| Transcript LLM | `cache/analysis/` | `{transcript_hash}_llm.json` | Until reanalysis | 100 MB |
| Thumbnails | `cache/thumbnails/` | `{frame_hash}.jpg` | 30 days | 1 GB |
| Proxy videos | `project/{id}/proxies/` | `{hash}_720p.mp4` | Per-project | Configurable |

---

## 8. Plugin Architecture

### 8.1 Plugin Discovery

```
Startup
  │
  ├── 1. Scan directories:
  │       ├── backend/infrastructure/plugins/builtins/ (built-in)
  │       └── ~/.localclip/plugins/ (user-installed)
  │
  ├── 2. For each plugin directory:
  │       ├── Read manifest.json
  │       ├── Validate against JSON Schema
  │       ├── Check min_app_version
  │       ├── Check Python dependency (pip list)
  │       └── Check model availability (optional)
  │
  ├── 3. If valid:
  │       ├── Import plugin module
  │       ├── Instantiate plugin class
  │       └── Call plugin.load()
  │
  └── 4. Register in PluginRegistry:
        ├── By type (STT, LLM, Vision, etc.)
        └── By priority (user-configured)
```

### 8.2 Plugin Isolation

```
┌──────────────────────────────────────────────┐
│              PLUGIN SANDBOX                    │
│                                                │
│  Plugin Process (subprocess, optional)         │
│  ┌────────────────────────────────────────┐    │
│  │ Restricted Python Environment          │    │
│  │                                        │    │
│  │ Permissions enforced:                  │    │
│  │ • Filesystem: Read models/, Read/write │    │
│  │   temp/ only                           │    │
│  │ • Network: Configured provider URLs    │    │
│  │   only                                 │    │
│  │ • GPU: Through HAL interface (quota)   │    │
│  │ • Timeout: Max 30 min per call         │    │
│  │ • Memory: 4 GB limit                   │    │
│  │                                        │    │
│  │ Communication: JSON-RPC over stdin/    │    │
│  │   stdout (or in-process direct call)   │    │
│  └────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

### 8.3 Plugin Registration

```python
# Registration data model
@dataclass
class PluginRegistration:
    name: str
    version: str
    type: PluginType  # stt, llm, vision, caption, translation, export
    instance: PluginBase
    manifest: dict
    status: PluginStatus  # DISCOVERED, LOADED, INITIALIZED, ACTIVE, ERROR, DISABLED
    priority: int  # 0 (highest) to 100 (lowest)
    capabilities: set[str]
    health: PluginHealth  # last health check result


class PluginRegistry:
    _plugins: dict[PluginType, list[PluginRegistration]]

    def register(self, registration: PluginRegistration) -> None: ...
    def get_providers(self, plugin_type: PluginType) -> list[PluginRegistration]: ...
    def get_best_provider(self, plugin_type: PluginType) -> PluginRegistration | None:
        """Return highest-priority ACTIVE provider for the given type."""
        ...
    def health_check_all(self) -> dict[str, PluginHealth]: ...
    def shutdown_all(self) -> None: ...
```

### 8.4 Supported Plugin Types

| Type | Interface | Examples | Capabilities |
|------|-----------|----------|--------------|
| `stt` | `STTProvider` | WhisperX, SenseVoice, OpenAI Whisper | diarization, word_timestamps, language_detection |
| `llm` | `LLMProvider` | Qwen, Llama, GPT, Claude | semantic_analysis, content_gen, summarization |
| `vision` | `VisionProvider` | YOLO, SAM, OpenCV | face_detection, object_tracking, scene_classification |
| `caption` | `CaptionProvider` | Built-in animated, ASS renderer | word_highlight, karaoke, emoji_insertion |
| `translation` | `TranslationProvider` | NLLB, Google Translate, DeepL | multi_language, auto_detect, preserve_timing |
| `export` | `ExportProvider` | MP4, MOV, WebM, XML, EDL | format_conversion, metadata_embedding |

---

## 9. Hardware Abstraction Layer

### 9.1 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    HARDWARE ABSTRACTION LAYER                  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    HALRegistry                          │  │
│  │  - Backend detection on startup                        │  │
│  │  - Priority selection: CUDA > MPS > ROCM > CPU         │  │
│  │  - Memory budget management                            │  │
│  │  - Per-model memory allocation                         │  │
│  └──────────────────────┬─────────────────────────────────┘  │
│                         │                                     │
│         ┌───────────────┼───────────────┐                     │
│         │               │               │                     │
│         ▼               ▼               ▼                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                │
│  │   CUDA   │    │   MPS    │    │  ROCM    │    ┌──────────┐│
│  │ Provider │    │ Provider │    │ Provider │    │   CPU    ││
│  │          │    │          │    │          │    │ Provider ││
│  │ • nvidia  │    │ • mps    │    │ • amd    │    │ • torch  ││
│  │   smi     │    │   backend│    │   hip    │    │   device ││
│  │ • torch   │    │ • torch  │    │ • torch  │    │   = cpu  ││
│  │   cuda    │    │   mps    │    │   hip    │    │          ││
│  │ • cuda    │    │          │    │          │    │          ││
│  │   streams │    │          │    │          │    │          ││
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘│
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                 MemoryManager                           │  │
│  │  - Track allocated VRAM                                │  │
│  │  - Enforce per-model limits                            │  │
│  │  - Automatic fallback on OOM                           │  │
│  │  - Configurable headroom (default 20% reserved)        │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 9.2 Backend Detection Algorithm

```python
def detect_and_select_backend() -> HALProvider:
    """Auto-detect best available GPU backend."""
    backends = [
        ("CUDA", CUDAProvider, (
            torch.cuda.is_available()
            and torch.version.cuda is not None
        )),
        ("MPS", MPSProvider, (
            torch.backends.mps.is_available()
            and torch.backends.mps.is_built()
        )),
        ("ROCm", ROCmProvider, (
            torch.cuda.is_available()
            and torch.version.hip is not None
        )),
        ("CPU", CPUProvider, lambda: True),  # Always available
    ]

    for name, provider_cls, available_fn in backends:
        if available_fn():
            provider = provider_cls()
            provider.initialize()
            return provider

    return CPUProvider()  # Fallback
```

### 9.3 HAL Interface (Consumer View)

```python
# What every AI module sees:
hal = HALRegistry.get_active_backend()

# Move model to device
model = model.to(hal.get_device())

# Move data to device
audio_tensor = hal.to_device(audio_tensor)

# Get optimal batch size
batch_size = hal.get_optimal_batch_size(
    model_size_mb=3000,
    available_memory_mb=hal.get_device_info().vram_available_bytes // (1024*1024)
)

# Memory management
hal.memory_cleanup()

# NEVER do:
# torch.cuda.is_available()         # ❌ Wrong
# model.cuda()                      # ❌ Wrong
# audio_tensor.to('cuda')           # ❌ Wrong
```

---

## 10. Cross-Cutting Concerns

### 10.1 Logging

`ARCH-CC-001`: All logging SHALL use structured JSON format with the following schema:

```json
{
  "timestamp": "2026-06-29T10:00:00.000Z",
  "level": "INFO|WARNING|ERROR|CRITICAL",
  "logger": "backend.services.import_service",
  "request_id": "req-abc-123",
  "correlation_id": "corr-xyz-789",
  "message": "Video import completed",
  "details": {
    "project_id": "proj-uuid",
    "video_id": "vid-uuid",
    "duration_ms": 1234,
    "file_size_bytes": 524288000
  },
  "duration_ms": 1234,
  "exception": null
}
```

`ARCH-CC-002`: Log files SHALL rotate daily, retaining 30 days. Max 500 MB per file. [P0]

`ARCH-CC-003`: Every log entry MUST include `request_id` for correlation tracing through the system. [P0]

`ARCH-CC-004`: The following SHALL NOT be logged: API keys, passwords, file contents, user paths (use relative paths). [P0]

### 10.2 Configuration

`ARCH-CC-005`: Configuration SHALL be loaded from `~/.localclip/config/settings.json` at startup. [P0]

`ARCH-CC-006`: Configuration SHALL be validated against a Pydantic schema on load. Invalid config SHALL be rejected with a clear error. [P0]

`ARCH-CC-007`: Configuration changes SHALL take effect without application restart where possible. Services SHALL poll for config changes or receive push notifications. [P1]

### 10.3 Error Handling

`ARCH-CC-008`: Every error MUST be: logged with full context, recoverable where possible, and presented to the user with an explanation and suggested fix. [P0]

`ARCH-CC-009`: The error propagation chain SHALL be: `Exception → Service → Route Handler → Error Middleware → JSON Error Response`. [P0]

`ARCH-CC-010`: Unhandled exceptions in async routes SHALL be caught by FastAPI's exception handler. Unhandled exceptions in Celery tasks SHALL be caught by Celery's error handler. [P0]

### 10.4 Dependency Injection

`ARCH-CC-011`: All service dependencies SHALL be injected through constructor injection. No service SHALL instantiate its own dependencies. [P0]

`ARCH-CC-012`: FastAPI's dependency injection system SHALL be used for request-scoped dependencies (DB sessions, request ID). [P0]

`ARCH-CC-013`: A central `deps.py` module SHALL define all dependency providers. [P0]

```python
# Example DI pattern
def get_project_service(
    repo: ProjectRepository = Depends(get_project_repo),
    fs: FileSystemService = Depends(get_filesystem_service),
) -> ProjectService:
    return ProjectService(repo, fs)
```

### 10.5 Security

`ARCH-CC-014`: All file path inputs MUST be validated against path traversal. Use `resolved_path.relative_to(allowed_base)` pattern. [P0]

`ARCH-CC-015`: API keys MUST be encrypted at rest using `cryptography.fernet.Fernet` with a machine-derived key. [P0]

`ARCH-CC-016`: The application MUST NOT make outbound network connections except: user-initiated model downloads, user-configured AI providers, user-initiated YouTube imports. [P0]

### 10.6 Performance

`ARCH-CC-017`: All GPU-bound operations SHALL go through `HALRegistry`. [P0]

`ARCH-CC-018`: Proxy videos SHALL be generated on import and used for all timeline editing. Source videos SHALL only be used for export. [P0]

`ARCH-CC-019`: Cached analysis results SHALL be reused when re-processing the same video with identical parameters. Cache key = hash of (video_hash + pipeline_params). [P0]

`ARCH-CC-020`: Long-running operations (> 5 seconds) SHALL be executed as Celery background tasks. No operation SHALL block the API response for more than 5 seconds. [P0]

---

## 11. Coding Standards

### 11.1 Architectural Rules

| Rule | Description | Enforcement |
|------|-------------|-------------|
| **R-001** | Domain layer must have zero imports from infrastructure | pytest-arch |
| **R-002** | Services must only import from domain and infrastructure interfaces | pytest-arch |
| **R-003** | API layer must only import from services (never repositories) | Code review |
| **R-004** | No module may import `torch.cuda` directly — use HAL | Code review |
| **R-005** | No module may import `whisperx`, `yolo`, etc. directly — use plugins | Code review |
| **R-006** | All public functions must have type annotations | mypy strict |
| **R-007** | All service methods must have docstrings with raises documented | Ruff |
| **R-008** | No bare `except:` — always catch specific exceptions | Ruff |
| **R-009** | All file paths must be validated for traversal | Pytest |
| **R-010** | Every new feature must include tests | CI gate |

### 11.2 Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| **Python modules** | snake_case | `project_service.py` |
| **Python classes** | PascalCase | `ProjectService` |
| **Python functions** | snake_case | `get_project_by_id` |
| **Python variables** | snake_case | `project_video` |
| **TypeScript modules** | camelCase | `projectService.ts` |
| **TypeScript components** | PascalCase | `ProjectBrowser.tsx` |
| **TypeScript functions** | camelCase | `getProjectById` |
| **TypeScript variables** | camelCase | `projectVideo` |
| **SQLAlchemy models** | PascalCase | `ProjectVideo` |
| **Database tables** | snake_case | `project_videos` |
| **API endpoints** | kebab-case | `/api/v1/project-videos` |
| **JSON keys** | snake_case | `project_id` |
| **Environment variables** | UPPER_SNAKE | `LOCALCLIP_STORAGE_PATH` |
| **Configuration keys** | dot.separated | `storage.proxy.enabled` |

### 11.3 Package Organization Rules

| Rule | Description |
|------|-------------|
| **One module per file** | No monolithic files over 500 lines. Split into modules. |
| **`__init__.py` exports** | Public API exports only. Internal modules are prefixed with `_`. |
| **Repository pattern** | Every entity has a repository interface in domain and implementation in infrastructure. |
| **Interface-first** | Define interfaces before implementations. |
| **No leaked imports** | `plugin.py` file can import external AI libraries; service layer cannot. |

### 11.4 Folder Conventions

```
{module}/
├── __init__.py        # Public API exports
├── interface.py       # Interfaces/abstract classes
├── implementations/   # Concrete implementations
│   ├── __init__.py
│   ├── impl_a.py
│   └── impl_b.py
└── _utils.py          # Internal helpers (prefixed with _)
```

### 11.5 Error Propagation Rules

```
1. Domain exceptions: ValueError, custom domain exceptions
    → Caught by service layer
    → Converted to application exceptions
    → Logged with request_id + context

2. Infrastructure exceptions: DatabaseError, FileNotFoundError
    → Caught by service layer
    → Wrapped in application error with error code
    → User message: actionable + helpful

3. Plugin exceptions: PluginCrashedError, TimeoutError
    → Caught by plugin service
    → Fallback to next plugin in chain
    → If no fallback: return error with plugin info
```

---

## 12. Architecture Decision Records

See [docs/architecture/adr/INDEX.md](adr/INDEX.md) for the complete list of ADRs.

The following ADRs are defined:

| ADR | Title | Status |
|-----|-------|--------|
| ADR-001 | React Frontend with TypeScript | Approved |
| ADR-002 | Python FastAPI Backend | Approved |
| ADR-003 | SQLite as Primary Database | Approved |
| ADR-004 | SQLAlchemy 2.0 ORM | Approved |
| ADR-005 | REST API with FastAPI | Approved |
| ADR-006 | WebSocket for Real-Time Events | Approved |
| ADR-007 | Plugin-Based AI Provider Architecture | Approved |
| ADR-008 | Hardware Abstraction Layer | Approved |
| ADR-009 | Local-First Application Design | Approved |
| ADR-010 | Structured Storage Layout | Approved |
| ADR-011 | AI Provider Abstraction with Fallback | Approved |
| ADR-012 | Celery for Background Job Queue | Approved |
| ADR-013 | FFmpeg Subprocess Integration | Approved |
| ADR-014 | No Authentication Architecture | Approved |
| ADR-015 | Domain-Driven Design | Approved |
| ADR-016 | CQRS for Analysis Read Models | Proposed |

---

## 13. Quality Gate Review

### 13.1 Review Checklist

| # | Concern | Status | Evidence |
|---|---------|--------|----------|
| 1 | **Architectural consistency** — all layers align with DDD principles | ✅ PASS | Domain → Service → Infrastructure layering is strict; interfaces defined |
| 2 | **Dependency correctness** — no circular or inverted deps | ✅ PASS | Dependency graph in §4 shows acyclic directed graph; import rules in §4.2 |
| 3 | **Layer isolation** — domain has no framework imports | ✅ PASS | §11.1 R-001 enforces this; domain depends on nothing |
| 4 | **Modularity** — components have single responsibilities | ✅ PASS | §3.2 defines responsibilities; modules are < 500 lines each |
| 5 | **Extensibility** — new AI providers can be added without code changes | ✅ PASS | §8 Plugin Architecture; add plugin manifest + implementation file |
| 6 | **Performance** — GPU abstraction, proxy editing, caching | ✅ PASS | §9 HAL, §7.5 caching, §6.6 proxy editing |
| 7 | **Scalability** — single-user architecture is not over-engineered | ✅ PASS | No distributed state; no service discovery; no load balancing |
| 8 | **Testability** — all components testable in isolation | ✅ PASS | DI pattern enables mocking; repository interfaces enable DB mocking |
| 9 | **Plugin compatibility** — well-defined interfaces | ✅ PASS | §8.3 plugin interfaces with formal input/output contracts |
| 10 | **Future maintainability** — no tech debt shortcuts | ✅ PASS | ADRs document trade-offs; no dead code paths; explicit clean interfaces |

### 13.2 Remaining Risks

| Risk | Mitigation | Owner |
|------|------------|-------|
| Plugin sandboxing adds complexity; subprocess overhead | Start with in-process plugin execution; add sandboxing as P2 | Architecture |
| GPU memory contention between worker processes | Worker count matched to GPU memory budget; fallback to serial execution | Performance |
| FFmpeg version differences across OS | Pin minimum version; document installation per OS; use well-tested command flags | DevOps |

---

## 14. References

| Document | Location |
|----------|----------|
| Vision Document | `docs/vision/VISION_DOCUMENT.md` |
| Product Requirements Document | `docs/PRD.md` |
| Software Requirements Specification | `docs/SRS.md` |
| Architecture Decision Records | `docs/architecture/adr/` |

---

*End of Architecture Blueprint*
