# Local Clip Studio — Vision Document

> **Status:** ✅ FINAL — APPROVED  
> **Version:** 2.0  
> **Date:** 2026-06-29  
> **Author:** Principal Engineering Team  
> **Approval:** All immutable architectural decisions locked. This document is the single source of truth.

---

## 1. Executive Summary

**Local Clip Studio** is a local-first, AI-powered video editing application that transforms long-form videos into short-form vertical clips automatically. Inspired by OpusClip, CapCut Desktop, and DaVinci Resolve, it runs entirely on the user's local machine with no cloud dependencies, no authentication, and no multi-user infrastructure.

The application combines professional-grade video editing capabilities with AI-driven automation — speech-to-text, speaker diarization, scene detection, semantic analysis, hook detection, and automatic clip generation — all powered by local open-weight AI models with optional external AI provider support.

---

## 2. Product Vision

> *"A desktop-grade video editing experience through the browser — combining the AI automation of OpusClip with the professional editing capabilities of DaVinci Resolve, running entirely on a single local machine for a single user."*

---

## 3. IMMUTABLE ARCHITECTURAL DECISIONS

The following decisions are locked and **cannot be changed** without a full project review.

### 3.1 Project Identity

| Attribute | Immutable Decision |
|-----------|-------------------|
| **Nature** | Local-first AI web application |
| **Not** | SaaS platform, commercial product, cloud service |
| **Intended Use** | Personal use only |
| **Architecture** | Browser is UI only; all processing on local machine |
| **Ownership** | Single user, single machine |

### 3.2 Authentication — ABSOLUTELY NONE

The following will **never** exist in this codebase:

❌ Login, registration, user accounts, passwords  
❌ Authentication, OAuth, JWT, sessions  
❌ Multi-user support, teams, workspaces, organizations  
❌ Billing, subscriptions, licensing  
❌ Cloud user management of any kind  
❌ Any auth-related code, dependencies, or infrastructure

**Behavior:** The application always opens directly into the Project Browser or restores the last opened project. No login screen. No auth gate.

### 3.3 Backend Architecture

| Component | Locked Decision |
|-----------|----------------|
| **Frontend** | React + TypeScript + Vite + Tailwind CSS + shadcn/ui |
| **Backend** | Python FastAPI |
| **Database** | SQLite (default), optional PostgreSQL in future |
| **Media Processing** | FFmpeg |
| **AI Runtime** | PyTorch, ONNX Runtime |
| **Realtime** | WebSocket for progress updates |
| **API** | REST API for application logic |
| **Convex** | ❌ MUST BE COMPLETELY REMOVED — all dependencies eliminated |

### 3.4 AI Provider Philosophy

The application **must** support both modes:

| Mode | Status |
|------|--------|
| **Local AI models** | ✅ Default mode — fully offline |
| **External API providers** | ✅ Optional — user-configurable |

Supported external providers:
- Ollama (local API)
- LM Studio (local API)
- OpenAI-compatible endpoints
- OpenAI
- Anthropic
- Google Gemini
- OpenRouter
- Groq
- NVIDIA NIM
- Together AI
- Fireworks
- DeepInfra
- Mistral AI

**Constraints:** API keys stored locally only. No login ever required. No telemetry. No key sync.

### 3.5 GPU Strategy

**Hardware Abstraction Layer required.** Never hardcode CUDA.

| Priority | Backend |
|----------|---------|
| 1 | CUDA (NVIDIA) |
| 2 | Apple Metal (MPS) |
| 3 | ROCm (AMD) |
| 4 | CPU fallback |

Each AI component selects the best available backend at runtime.

### 3.6 Plugin System Architecture

Every AI component must be replaceable via plugins:

| Plugin Domain | Examples |
|---------------|----------|
| Speech-to-Text | WhisperX, SenseVoice, OpenAI Whisper API |
| Vision | YOLO, SAM, OpenCV, GPT-4 Vision |
| LLM | Qwen, Llama, Gemma, OpenAI, Anthropic |
| Caption Engine | Built-in animated, third-party |
| Translation | Local NLLB, Google Translate, DeepL |
| Export | MP4, MOV, WebM, XML, EDL, SRT |

**Rule:** Core application must never depend directly on a single AI provider.

### 3.7 Performance Target Hardware

| Component | Target Spec | Graceful Degradation |
|-----------|-------------|---------------------|
| **GPU** | RTX 3060+ | Any CUDA-capable GPU → CPU |
| **Apple Silicon** | M1+ | MPS acceleration → CPU |
| **Storage** | NVMe SSD | Any SSD → HDD (slower) |
| **RAM** | 32GB | 16GB minimum |
| **Processing** | Proxy editing | Direct editing on low-end |

### 3.8 Storage Philosophy

Structured project directory with clear separation:

```
~/.localclip/
├── projects/          # Project metadata & assets
├── sources/           # Original imported videos
├── proxies/           # Proxy-encoded videos
├── cache/             # Processing cache (frames, audio chunks)
├── models/            # Downloaded AI models
├── exports/           # Rendered output files
├── logs/              # Structured JSON logs
├── temp/              # Temporary processing files
└── config/            # User configuration
```

Features: Automatic cleanup, configurable storage limits, selective purge.

### 3.9 Coding Philosophy — Immutable Standards

| Principle | Application |
|-----------|-------------|
| **Clean Architecture** | Layers: Presentation → Application → Domain → Infrastructure |
| **SOLID** | Single responsibility, open-closed, Liskov, interface segregation, dependency inversion |
| **Domain-Driven Design** | Ubiquitous language: Project, Clip, Scene, Transcript, Caption |
| **Dependency Injection** | All cross-cutting concerns injected |
| **Repository Pattern** | Data access abstracted behind interfaces |
| **Plugin Architecture** | AI providers, export formats, caption engines as swappable plugins |
| **Testability** | Every component testable in isolation |
| **No shortcuts** | Never optimize for implementation speed at the expense of architecture |

---

## 4. Complete Feature Scope (v1.0)

All features listed below are **in-scope** for v1.0 planning. They may be scheduled across milestones, but the architecture must accommodate all of them.

| Domain | Features |
|--------|----------|
| **🎬 Video Import** | Local file, drag & drop, YouTube URL, batch import, folder import, metadata preview |
| **🧠 AI Analysis** | STT, speaker diarization, scene detection, silence detection, topic segmentation, semantic analysis, hook detection, virality scoring, quality score, highlight detection, emotion detection, keyword extraction, chapter generation |
| **✂️ AI Clip Generation** | Auto clip generation, multiple candidates, smart trimming, clip ranking, merging, duplicate removal, auto title/description/hashtags |
| **🎥 Smart Editing** | Timeline editor, text-based editing, split, trim, ripple delete, undo/redo, multi-track timeline, audio waveform, markers, snapping, keyboard shortcuts |
| **🎞 AI Reframe** | Face tracking, speaker tracking, object tracking, smart crop, multi-person framing, H→V, H→Square, H→Portrait |
| **🔍 Auto Zoom** | Speaker emphasis, emotion emphasis, keyword emphasis, volume spike detection, manual adjustment, zoom templates |
| **💬 Captions** | Animated, karaoke, word highlighting, emoji insertion, multiple presets, font library, animation editor |
| **🌍 Translation** | Multi-language, auto-detection, subtitle/caption translation, voice translation (optional) |
| **🎙 AI Voice** | Voice enhancement, noise reduction, normalization, silence removal, voice cloning, AI dubbing |
| **🎨 AI Visual** | Thumbnail generator, B-roll suggestion/generation, stock footage suggestion, AI image generation |
| **✍ AI Content** | Title generator, description, hashtags, SEO, CTA, hook improvement, script summarization |
| **🤖 AI Assistants** | Editing assistant, chat about video, prompt assistant, content coach, SEO coach |
| **📦 Export** | MP4, MOV, WebM, XML, EDL, Premiere XML, DaVinci XML, Final Cut XML, SRT, VTT, ASS, JSON metadata |
| **⚙ Batch Processing** | Multiple videos, queue system, background jobs, resume, scheduled processing |
| **🗂 Project Management** | Project browser, auto save, version history, backup, restore, duplicate, archive |
| **🔌 AI Provider Mgmt** | 14+ providers, enable/disable, API key, base URL, model, temperature, timeout, retry, fallback |
| **🧩 Plugin System** | AI, export, caption, translation, video effect, import plugins |
| **📊 Processing Analytics** | Clip quality score, virality, hook analysis, engagement prediction, readability, speaking speed, silence ratio, keyword frequency, emotion timeline |
| **🎨 UI** | Dark/light mode, custom themes, dockable panels, multi-window layout, workspace presets |
| **⚡ Performance** | GPU acceleration (CUDA/ROCm/Metal), proxy editing, incremental rendering, smart cache, multi-thread |
| **⚙ Settings** | General, Appearance, Storage, GPU, AI Models, AI Providers, API Keys, Export, Keyboard, Cache, Advanced |

---

## 5. AI Pipeline Architecture

```
Input Video
    │
    ▼
┌─────────────────────────────┐
│ FFmpeg Preprocessing        │
│ • Transcoding               │
│ • Audio extraction          │
│ • Frame extraction          │
│ • Proxy generation          │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Speech Recognition          │
│ (WhisperX / SenseVoice)     │
│ • Word-level timestamps     │
│ • Speaker diarization       │
│ • Language detection        │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Visual Analysis             │
│ • Scene detection (PyScene) │
│ • Face tracking (YOLO)      │
│ • Object tracking (SAM)     │
│ • Emphasis detection        │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Semantic Analysis (LLM)     │
│ • Topic segmentation        │
│ • Hook detection            │
│ • Virality scoring          │
│ • Quality scoring           │
│ • Chapter generation        │
│ • Keyword extraction        │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Clip Generation Engine      │
│ • Candidate extraction      │
│ • Smart trimming            │
│ • Clip ranking              │
│ • Duplicate removal         │
│ • Merge overlapping         │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Rendering Pipeline          │
│ • Smart reframe (9:16, 1:1) │
│ • Auto zoom effects         │
│ • Caption overlay           │
│ • Timeline compositing      │
│ • GPU-accelerated encoding  │
└──────────┬──────────────────┘
           │
           ▼
          Export
```

---

## 6. Quality Score Dimensions (0–100)

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Hook Strength | 25% | Compelling opening within first 3 seconds? |
| Content Density | 20% | Information density per second — minimal dead air |
| Audio Clarity | 15% | Speech clarity, noise floor, speaker intelligibility |
| Visual Variety | 15% | Shot changes, camera movement, on-screen activity |
| Structural Completeness | 15% | Beginning, middle, and end present? |
| Engagement Potential | 10% | Predicted retention based on pacing, emphasis, hooks |

---

## 7. Studio Theme Design

### Visual Direction

- **Default mode:** Dark (professional video editing convention)
- **Light mode:** Warm off-whites with muted neutrals
- **Color palette:** Muted earth tones, warm grays, thin stroke borders
- **Typography:** Clean sans-serif for UI, monospace for timeline/timing
- **Spacing:** Generous whitespace with careful editorial rhythm
- **Panels:** Dockable, resizable, collapsible — DaVinci Resolve inspired

### UI Philosophy

> *"Not a website — a professional tool. The browser is just the rendering engine."*

- No marketing pages, no pricing, no subscription UI
- No login screens — app opens directly into editor workspace
- Keyboard-first workflow with desktop-grade shortcuts
- Gallery-clean, refined, editorial presentation

---

## 8. Quality Gates & Engineering Standards

| Standard | Requirement |
|----------|-------------|
| **Error Handling** | Every error logged, recoverable, with explanation + fix guidance. Never crash silently. |
| **Logging** | Structured JSON logs, rotation, correlation IDs, performance metrics, processing history |
| **Testing** | Unit tests + Integration tests + E2E tests + Performance benchmarks + Regression tests |
| **Security** | Upload validation, path traversal prevention, plugin sandboxing, secure file handling |
| **Privacy** | Zero telemetry, zero tracking, zero cloud storage, zero data leakage. No user tracking. |
| **Performance** | Proxy editing, background processing, GPU acceleration, job queue, incremental processing, caching |
| **Architecture** | Clean Architecture, SOLID, DDD, Repository pattern, Plugin architecture, CQRS where appropriate |

---

## 9. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| AI model size (10-30GB download) | High | Medium | Show download progress, support model selection, incremental download |
| GPU compatibility varies by hardware | Medium | High | Abstraction layer, CPU fallback, user-selectable backend |
| FFmpeg dependency | Low | High | Bundle FFmpeg or provide clear install instructions |
| Processing time for long videos | High | Medium | Proxy editing, incremental processing, progress reporting |
| Python environment complexity | Medium | Medium | Setup script, virtualenv, dependency lockfile, pre-built wheels |
| Plugin security (external code execution) | Medium | High | Sandboxed execution, manifest validation, permission system |

---

## 10. Next Phase

**Phase 2: Product Requirements Document (PRD)**

Each feature will be expanded into:
- User Stories
- Functional Requirements
- Acceptance Criteria
- Edge Cases
- Data Flow
- Error Handling
- Dependencies
- Performance Targets
- UI Requirements
- API Requirements
- Storage Requirements
- AI Requirements
- Testing Considerations
- Unique Requirement ID with Priority (Must/Should/Could)
- Traceability to this Vision Document
