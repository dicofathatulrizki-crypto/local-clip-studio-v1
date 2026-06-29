# Local Clip Studio — Vision Document

> **Status:** Final  
> **Version:** 1.0  
> **Date:** 2026-06-29  
> **Author:** Principal Engineering Team

---

## 1. Executive Summary

**Local Clip Studio** is a local-first, AI-powered video editing application that transforms long-form videos into short-form vertical clips automatically. Inspired by OpusClip, CapCut Desktop, and DaVinci Resolve, it runs entirely on the user's local machine with no cloud dependencies, no authentication, and no multi-user infrastructure.

The application combines professional-grade video editing capabilities with AI-driven automation — speech-to-text, speaker diarization, scene detection, semantic analysis, hook detection, and automatic clip generation — all powered by local open-weight AI models.

---

## 2. Product Vision

> *"A desktop-grade video editing experience through the browser — combining the AI automation of OpusClip with the professional editing capabilities of DaVinci Resolve, running entirely on a single local machine for a single user."*

---

## 3. Confirmed Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Backend** | Pure Python FastAPI | Replace Convex entirely. Required for local FFmpeg, GPU-accelerated AI inference, file system access, background workers |
| **Frontend** | React + Vite + TypeScript + Tailwind + shadcn/ui | Existing project foundation — keep and extend |
| **Authentication** | None | Single-user, no login, no accounts, no auth code whatsoever |
| **Database** | SQLite via SQLAlchemy + Alembic | Local-first, zero-config, migration-supported |
| **GPU Support** | CUDA + ROCm + Metal | Abstraction layer to support NVIDIA, AMD, and Apple Silicon |
| **Job Queue** | Celery + Redis (optional) | For background AI pipeline processing |
| **AI Models** | Local open-weight only (default) | WhisperX, YOLO, SAM, Qwen/Llama, ONNX Runtime |
| **AI Providers** | Plugin architecture for future external APIs | Ollama, LM Studio, OpenAI, Anthropic, etc. as optional addons |

---

## 4. Core Product Identity

| Attribute | Value |
|-----------|-------|
| **Name** | Local Clip Studio |
| **Platform** | Localhost web app (desktop-class experience) |
| **Target User** | Single person on a single machine |
| **Internet Required** | Only for model download + optional YouTube import |
| **Primary Stack** | Python FastAPI (backend) + React/TypeScript (frontend) |
| **Primary Storage** | SQLite + local filesystem |
| **Default AI** | Local open-weight models only |
| **Theme** | Studio — warm off-whites, muted neutrals, thin framing, editorial cleanliness |

---

## 5. High-Level Feature Map

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL CLIP STUDIO                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Video Import │  │ AI Pipeline  │  │ Project Manager  │   │
│  │ • Local file │  │ • STT        │  │ • Create/Save    │   │
│  │ • Drag&drop  │  │ • Diarization│  │ • Auto-save      │   │
│  │ • YouTube    │  │ • Scene det  │  │ • Version hist.  │   │
│  │ • Batch      │  │ • Hook score │  │ • Archive        │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────┘   │
│         │                  │                                 │
│         ▼                  ▼                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  TIMELINE EDITOR                     │   │
│  │  • Split • Trim • Waveform • Transcript sync         │   │
│  │  • Smart reframe • Auto zoom • Captions              │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                     EXPORT                           │   │
│  │  MP4 │ MOV │ WebM │ SRT │ VTT │ EDL │ XML │ JSON    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ AI Provider  │  │ Settings     │  │ Batch Queue      │   │
│  │ Manager      │  │ • GPU        │  │ • Multiple vids  │   │
│  │ • Local/Ollam│  │ • Storage    │  │ • Background     │   │
│  │ • OpenAI/etc │  │ • Keyboard   │  │ • Resume         │   │
│  └─────────────┘  └──────────────┘  └──────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. AI Pipeline Architecture

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

## 7. Quality Score Dimensions (0–100)

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Hook Strength | 25% | Does the clip have a compelling opening within first 3 seconds? |
| Content Density | 20% | Information density per second — minimal dead air |
| Audio Clarity | 15% | Speech clarity, noise floor, speaker intelligibility |
| Visual Variety | 15% | Shot changes, camera movement, on-screen activity |
| Structural Completeness | 15% | Does the clip have a beginning, middle, and end? |
| Engagement Potential | 10% | Predicted retention based on pacing, emphasis, and hooks |

---

## 8. Studio Theme Design

### Visual Direction

- **Default mode:** Dark (professional video editing convention)
- **Light mode:** Warm off-whites with muted neutrals
- **Color palette:** Muted earth tones, warm grays, thin stroke borders
- **Typography:** Clean sans-serif for UI, monospace for timeline/timing
- **Spacing:** Generous whitespace with careful editorial rhythm
- **Panels:** Dockable, resizable, collapsible — DaVinci Resolve inspired

### UI Philosophy

> *"Not a website — a professional tool. The browser is just the rendering engine."*

- No marketing pages
- No pricing or subscription UI
- No login screens
- App opens directly into the editor workspace
- Keyboard-first workflow with desktop-grade shortcuts

---

## 9. Non-Goals (Explicit Exclusion List)

The following are strictly out of scope:

❌ User authentication, login, registration, accounts, passwords  
❌ Multi-user support, teams, workspaces, organizations  
❌ Subscription, billing, credit systems, payment gateways  
❌ Cloud rendering, cloud storage, cloud dependencies  
❌ User analytics, telemetry, CRM, customer dashboards  
❌ Email verification, notifications, customer messaging  
❌ Admin panels, role-based access control  
❌ Affiliate systems, referral programs, marketplaces  
❌ Multi-tenant database design  
❌ Any customer-facing SaaS infrastructure  

---

## 10. Quality Gates & Engineering Standards

| Standard | Requirement |
|----------|-------------|
| **Error Handling** | Every error logged, recoverable, with explanation + fix guidance |
| **Logging** | Structured JSON logs, rotation, correlation IDs, performance metrics |
| **Testing** | Unit tests + Integration tests + E2E tests + Performance benchmarks |
| **Security** | Upload validation, path traversal prevention, plugin sandboxing |
| **Privacy** | Zero telemetry, zero tracking, zero cloud storage, zero data leakage |
| **Performance** | Proxy editing, background processing, GPU acceleration, caching |
| **Architecture** | Clean Architecture, SOLID, DDD, Repository pattern, Plugin architecture |

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **AI model size** (10-30GB download) | High | Medium | Show download progress, support model selection, incremental download |
| **GPU compatibility** varies by hardware | Medium | High | Abstraction layer, CPU fallback, user-selectable backend |
| **FFmpeg dependency** | Low | High | Bundle FFmpeg or provide clear install instructions |
| **Processing time** for long videos | High | Medium | Proxy editing, incremental processing, progress reporting |
| **Python environment** complexity | Medium | Medium | Provide setup script, virtualenv, dependency lockfile |

---

## 12. Next Phase

**Proceed to Phase 2: Product Requirements Document (PRD)**

The PRD will expand each feature into detailed requirements with acceptance criteria, user stories, and functional specifications.
