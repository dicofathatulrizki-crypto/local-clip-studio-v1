# Local Clip Studio

A local-first, AI-powered video editing application that transforms long-form videos into short-form vertical clips automatically. Inspired by OpusClip, CapCut Desktop, and DaVinci Resolve.

> **This is a personal-use tool.** It runs entirely on your own machine. No cloud, no accounts, no subscriptions. All AI processing is done locally with open-weight models.

---

## Features

- **🎬 Video Import** — Import MP4, MOV, MKV, AVI, WebM. Drag & drop, batch import, YouTube URL
- **🧠 AI Analysis** — Speech-to-text, speaker diarization, scene detection, hook detection, quality scoring
- **✂️ Auto Clip Generation** — AI-powered clip extraction with smart trimming and ranking
- **🎥 Timeline Editor** — Multi-track timeline with waveform, split/trim, keyboard shortcuts
- **🎞 Smart Reframe** — AI-driven crop from horizontal to vertical (9:16, 1:1, 4:5)
- **💬 Captions** — Animated, karaoke-style, multi-language
- **📦 Export** — MP4, MOV, WebM, SRT, VTT, ASS, EDL, XML

## Architecture

The application follows Clean Architecture with strict layer separation:

```
┌──────────────────────────────────────────────────────────┐
│  UI Layer — React SPA (Vite + TypeScript + shadcn/ui)    │
├──────────────────────────────────────────────────────────┤
│  API Layer — FastAPI REST + WebSocket (port 8765)        │
├──────────────────────────────────────────────────────────┤
│  Service Layer — Business logic orchestration             │
├──────────────────────────────────────────────────────────┤
│  Domain Layer — Pure entities, value objects, events      │
├──────────────────────────────────────────────────────────┤
│  Infrastructure Layer                                     │
│  ┌────────┬────────┬────────┬────────┬────────┬────────┐  │
│  │ SQLite │  HAL   │ FFmpeg │ Queue  │ Plugins│Logging │  │
│  └────────┴────────┴────────┴────────┴────────┴────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- **Python 3.11+**
- **FFmpeg 6.0+** (for video processing)

### Setup

```bash
# 1. Install backend dependencies
pip install -e ".[dev]"

# 2. Run setup (creates directories, default config)
bash scripts/setup.sh

# 3. Start the development server
make dev
# Or: python -m backend
# Server starts at http://localhost:8765
# API docs at http://localhost:8765/docs
```

### Commands

| Command | Description |
|---------|-------------|
| `make dev` | Start backend server with hot reload |
| `make test` | Run all tests |
| `make test-unit` | Run unit tests only |
| `make lint` | Run ruff linter |
| `make typecheck` | Run mypy type checking |
| `make check` | Lint + typecheck + unit tests |
| `make db-upgrade` | Apply database migrations |

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite 7, Tailwind CSS 4, shadcn/ui |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Database | SQLite (SQLAlchemy 2.0, Alembic) |
| AI Runtime | PyTorch, ONNX Runtime |
| AI Models | WhisperX, YOLOv8, Qwen/Llama, PySceneDetect |
| Task Queue | Celery (filesystem broker) |
| Video | FFmpeg 6.0+ |
| GPU | CUDA, Apple Metal, ROCm, CPU fallback (via HAL) |

## Project Structure (Module A1: Foundation)

```
├── backend/
│   ├── __init__.py            # Package init, version
│   ├── __main__.py            # CLI entry point (python -m backend)
│   ├── main.py                # FastAPI application factory
│   ├── config/
│   │   ├── __init__.py        # Config package
│   │   ├── settings.py        # Pydantic settings with file/ENV loading
│   │   ├── defaults.py        # Default configuration values
│   │   └── encryption.py      # AES-256-GCM API key encryption
│   ├── api/
│   │   ├── __init__.py        # API package
│   │   ├── middleware.py      # CORS, request ID, timing middleware
│   │   └── deps.py            # Dependency injection providers
│   ├── domain/
│   │   └── __init__.py        # Domain layer (entities forthcoming)
│   ├── services/
│   │   └── __init__.py        # Service layer (business logic forthcoming)
│   └── infrastructure/
│       ├── __init__.py        # Infrastructure package
│       └── logging/
│           ├── __init__.py    # Structured JSON logging
│           ├── logger.py      # JSONFormatter, configure_logging
│           └── correlation.py # Request ID propagation
├── docker/
│   ├── Dockerfile             # Multi-stage Docker image
│   ├── docker-compose.yml     # Docker Compose services
│   └── .dockerignore          # Build context exclusions
├── scripts/
│   ├── setup.sh               # One-click project setup
│   ├── dev.sh                 # Development server launcher
│   └── download_models.sh     # AI model downloader
├── tests/
│   ├── conftest.py            # Shared pytest fixtures
│   ├── unit/
│   │   ├── test_config.py     # Settings tests
│   │   ├── test_encryption.py # API key encryption tests
│   │   ├── test_logging.py    # Logging infrastructure tests
│   │   └── test_errors.py     # Error handling framework tests
│   └── integration/
│       └── __init__.py        # Integration tests (forthcoming)
├── pyproject.toml             # Python project config + dependencies
├── Makefile                   # Build/test automation targets
├── .env.example               # Environment configuration template
└── .gitignore                 # Git ignore rules
```

## Module A1 — Project Foundation (Complete)

- **Project scaffold** — Package structure, dependency management, build system
- **Configuration system** — Pydantic settings with JSON file, environment variable, and default loading
- **API key encryption** — AES-256-GCM with machine-derived key
- **Logging infrastructure** — Structured JSON logging with rotation, correlation IDs, sensitive data filtering
- **Error handling framework** — Complete error catalog (20+ error codes), AppError class, FastAPI exception handlers
- **API foundation** — Application factory, CORS middleware, request ID/timing middleware, dependency injection
- **Docker support** — Multi-stage Dockerfile with GPU target, Docker Compose
- **Documentation** — README, setup scripts, model downloader

## Project Status

| Phase | Module | Status |
|-------|--------|--------|
| Phase 7 | Module A1 — Project Foundation | ✅ Complete |
| Phase 7 | Module A2 — Configuration System | ✅ Complete (integrated in A1) |
| Phase 7 | Module A3 — Logging Infrastructure | ✅ Complete (integrated in A1) |
| Phase 7 | Module A4 — Database Engine | 🔜 Next |
| Phase 7 | Module A5 — Filesystem Service | ⏳ Pending |
| Phase 7 | Module A6 — Hardware Abstraction Layer | ⏳ Pending |
| Phase 7 | Module A7 — FFmpeg Service | ⏳ Pending |
| Phase 7 | Module A8 — Plugin Registry | ⏳ Pending |
| Phase 8+ | Backend Core + AI Pipeline + Frontend | ⏳ Future |

## License

MIT — For personal use only.

---

*Built with AI assistance. Local-first, privacy-first, no cloud.*
