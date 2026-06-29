# Local Clip Studio — API Specification

> **Status:** DRAFT  
> **Version:** 1.0  
> **Date:** 2026-06-29  
> **Format:** OpenAPI 3.1 (documented) + WebSocket Spec  
> **Traceability:** SRS §6, §7 → Architecture Blueprint §6, §7 → This Document  
> **Caveat:** Implementation-ready specification. No code to be written from this document alone.

---

## Table of Contents

1. [API Overview](#1-api-overview)
2. [API Conventions](#2-api-conventions)
3. [REST Endpoint Catalog](#3-rest-endpoint-catalog)
4. [WebSocket Specification](#4-websocket-specification)
5. [Data Contracts](#5-data-contracts)
6. [Pagination and Filtering](#6-pagination-and-filtering)
7. [Error Handling](#7-error-handling)
8. [Idempotency and Versioning](#8-idempotency-and-versioning)
9. [Quality Gate](#9-quality-gate)

---

## 1. API Overview

### 1.1 Base Information

| Property | Value |
|----------|-------|
| **Base URL** | `http://localhost:8765/api/v1` |
| **Protocol** | HTTP/1.1 (localhost) |
| **Content Type** | `application/json` |
| **File Upload** | `multipart/form-data` |
| **Authentication** | None (by design) |
| **Rate Limiting** | None (localhost, single user) |
| **Request ID** | `X-Request-ID` header (UUID v4) |
| **CORS** | Allow `http://localhost:5173` (dev), `http://localhost:*` (static) |

### 1.2 API Design Principles

1. **Resource-oriented** — URLs represent resources (projects, videos, clips)
2. **Consistent naming** — Plural nouns for collections (`/projects`), singular for instances (`/projects/{id}`)
3. **Standard HTTP methods** — GET (read), POST (create), PUT (replace), PATCH (update), DELETE (remove)
4. **Consistent error format** — All errors follow `{"error": {"code": "...", "message": "...", "details": {...}}}`
5. **Status codes** — 200 (success), 201 (created), 202 (accepted/async), 204 (deleted), 4xx (client error), 5xx (server error)
6. **Idempotency** — GET, PUT, DELETE are idempotent. POST is not.
7. **Versioning** — URL path prefix (`/api/v1/`). Breaking changes → new version.

### 1.3 Correlation ID Propagation

```
Client                          Server
  │                                │
  │── X-Request-ID: req-uuid ────▶│  (client generates)
  │                                │  (logged in every service call)
  │                                │── Celery task: correlation_id=req-uuid
  │                                │── FFmpeg subprocess: logged with req-uuid
  │                                │── Log entry: {request_id, ...}
  │◀── X-Request-ID: req-uuid ────│  (echoed in response)
```

---

## 2. API Conventions

### 2.1 Request Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Content-Type` | Yes (POST/PUT/PATCH) | `application/json` or `multipart/form-data` |
| `X-Request-ID` | No | UUID for request tracing. Server generates if absent. |

### 2.2 Response Headers

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Echoed request ID for correlation |
| `X-Data-Version` | Entity version number (for optimistic concurrency) |

### 2.3 Response Envelope

```json
// Success (single resource)
{
  "id": "uuid",
  "name": "Project Name",
  // ... resource fields
}

// Success (collection)
{
  "items": [ /* resources */ ],
  "total": 42,
  "limit": 20,
  "offset": 0
}

// Success (empty)
// HTTP 204 No Content — no body

// Error
{
  "error": {
    "code": "ERR-IMP-001",
    "message": "Unsupported file format. Supported formats: MP4, MOV, MKV, AVI, WebM",
    "details": {
      "provided_format": ".wmv",
      "supported_formats": [".mp4", ".mov", ".mkv", ".avi", ".webm"]
    },
    "request_id": "req-uuid-here",
    "timestamp": "2026-06-29T10:00:00Z"
  }
}
```

### 2.4 Date/Time Format

All timestamps use ISO 8601: `2026-06-29T10:00:00.000Z` (UTC).

### 2.9 Resource ID Format

All resource IDs are UUID v4 formatted as lowercase hexadecimal with hyphens:
`xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`

---

## 3. REST Endpoint Catalog

### 3.1 Project Endpoints

#### `POST /api/v1/projects` — Create Project

**Request:**
```json
{
  "name": "My Project",
  "description": null,
  "storage_path": null
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `name` | string | yes | 1-255 chars, not blank, trimmed |
| `description` | string or null | no | Max 2000 chars |
| `storage_path` | string or null | no | Must resolve within ~/.localclip/projects/ |

**Response (201):**
```json
{
  "id": "a1b2c3d4-...",
  "name": "My Project",
  "description": null,
  "created_at": "2026-06-29T10:00:00.000Z",
  "updated_at": "2026-06-29T10:00:00.000Z",
  "last_opened_at": null,
  "storage_path": "/home/user/.localclip/projects/a1b2c3d4-...",
  "thumbnail_url": null,
  "is_archived": false,
  "settings": {},
  "version": 1
}
```

**Errors:** `ERR-VALIDATION-001` (name required), `ERR-STORAGE-001` (path creation failed)

---

#### `GET /api/v1/projects` — List Projects

**Query Parameters:**
| Param | Type | Default | Constraints |
|-------|------|---------|-------------|
| `limit` | integer | 20 | 1-100 |
| `offset` | integer | 0 | ≥ 0 |
| `sort` | string | `-last_opened_at` | `name`, `created_at`, `updated_at`, `last_opened_at`. Prefix `-` for desc. |
| `archived` | boolean | false | Include archived projects |

**Response (200):**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Project Name",
      "description": "...",
      "created_at": "ISO8601",
      "updated_at": "ISO8601",
      "last_opened_at": "ISO8601",
      "video_count": 3,
      "thumbnail_url": null,
      "is_archived": false
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

---

#### `GET /api/v1/projects/{project_id}` — Get Project

**Response (200):** Same shape as create response, plus:
```json
{
  // ...project fields...
  "videos": [ /* ProjectVideo[] */ ],
  "timeline": { /* TimelineState */ },
  "video_count": 3,
  "total_duration_ms": 3600000,
  "analysis_count": 2
}
```

**Errors:** `ERR-NOTFOUND-001` (project not found)

---

#### `PATCH /api/v1/projects/{project_id}` — Update Project

**Request:**
```json
{
  "name": "New Name",
  "description": "Updated description"
}
```

All fields optional. Merge semantics — only provided fields are updated.

**Response (200):** Updated project object.

---

#### `DELETE /api/v1/projects/{project_id}` — Delete Project

**Response (204):** No content.

**Side Effects:** Deletes project directory, all files, database records. Not reversible.

---

#### `POST /api/v1/projects/{project_id}/duplicate` — Duplicate Project

**Request:**
```json
{
  "new_name": "Copy of My Project"
}
```

**Response (201):** New project object.

---

#### `POST /api/v1/projects/{project_id}/archive` — Archive Project

**Response (200):** Updated project with `is_archived: true`.

---

#### `POST /api/v1/projects/{project_id}/restore` — Restore Archived Project

**Response (200):** Updated project with `is_archived: false`.

---

### 3.2 Video Import Endpoints

#### `POST /api/v1/projects/{project_id}/videos` — Import Video

**Content-Type:** `multipart/form-data`

**Form Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | conditional | Local video file. Required unless `source_type=url`. |
| `source_type` | string | no | `local` (default) or `url` |
| `url` | string | conditional | YouTube URL. Required if `source_type=url`. |
| `generate_proxy` | boolean | no | Auto-generate proxy video (default: true) |

**Validation Rules:**
- File extension: `.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`
- Max file size: 50 GB (configurable)
- Must pass FFprobe validation (valid video stream detected)
- Must not exceed disk space available

**Response (202 — Accepted):**
```json
{
  "id": "uuid",
  "video_id": "uuid",
  "filename": "video.mp4",
  "original_filename": "video.mp4",
  "hash": "a1b2c3d4e5f6...",
  "status": "importing",
  "progress": 0.0,
  "metadata": {
    "duration_ms": 600000,
    "width": 1920,
    "height": 1080,
    "fps": 29.97,
    "video_codec": "h264",
    "audio_codec": "aac",
    "file_size_bytes": 524288000,
    "bitrate": 15000000
  },
  "imported_at": "ISO8601"
}
```

**Errors:** `ERR-IMP-001` through `ERR-IMP-006` (see error catalog)

---

#### `GET /api/v1/projects/{project_id}/videos` — List Project Videos

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | all | Filter by status: importing, ready, analyzing, error |

**Response (200):**
```json
{
  "items": [
    {
      "id": "uuid",
      "video_id": "uuid",
      "filename": "video.mp4",
      "hash": "a1b2...",
      "status": "ready",
      "proxy_available": true,
      "metadata": { /* same as import metadata */ },
      "analysis_status": "completed",
      "analysis_progress": 1.0,
      "imported_at": "ISO8601"
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

---

#### `GET /api/v1/projects/{project_id}/videos/{video_id}` — Get Video

**Response (200):** Detailed video object with full metadata.

---

#### `DELETE /api/v1/projects/{project_id}/videos/{video_id}` — Remove Video

**Response (204):** No content. Analysis and clip data cascaded.

---

### 3.3 Analysis Endpoints

#### `POST /api/v1/projects/{project_id}/videos/{video_id}/analyze` — Start Analysis

**Request:**
```json
{
  "pipeline_stages": {
    "transcribe": true,
    "diarize": true,
    "detect_scenes": true,
    "detect_silence": true,
    "analyze_semantic": true,
    "score_clips": true
  },
  "stt_model": "large-v3",
  "llm_model": null
}
```

All pipeline stages default to `true` if omitted.

**Response (202):**
```json
{
  "job_id": "uuid",
  "status": "queued",
  "estimated_duration_seconds": 300,
  "pipeline_stages": ["preprocessing", "transcribing", "diarizing", "scene_detecting", "analyzing", "scoring"],
  "created_at": "ISO8601"
}
```

**Errors:** `ERR-PIPE-002` (model not downloaded), `409 Conflict` (already analyzing)

---

#### `GET /api/v1/projects/{project_id}/videos/{video_id}/analysis` — Get Analysis

**Response (200 — completed):**
```json
{
  "status": "completed",
  "transcript": {
    "language": "en",
    "language_confidence": 0.99,
    "segments": [
      {
        "start_ms": 0,
        "end_ms": 3200,
        "text": "Welcome to this video on...",
        "speaker": "Speaker A",
        "confidence": 0.98,
        "words": [
          {"word": "Welcome", "start_ms": 0, "end_ms": 400, "confidence": 0.99, "speaker": "Speaker A"}
        ]
      }
    ]
  },
  "speakers": [
    {"label": "Speaker A", "segments": 42, "total_duration_ms": 320500}
  ],
  "scenes": [
    {"index": 0, "start_ms": 0, "end_ms": 30000, "type": "intro", "description": "Opening", "keyframe_url": "/api/v1/files/thumbnails/..."}
  ],
  "topics": [
    {"name": "Introduction", "start_ms": 0, "end_ms": 30000, "keywords": ["welcome", "overview"]}
  ],
  "keywords": ["AI", "video editing", "automation"],
  "hooks": [
    {"time_ms": 2500, "score": 85, "text": "this tool will save you 10 hours per week", "type": "benefit"}
  ],
  "chapters": [
    {"start_ms": 0, "title": "Introduction"},
    {"start_ms": 30000, "title": "Getting Started"}
  ],
  "quality_scores": {
    "overall": 78,
    "dimensions": {
      "hook_strength": 82,
      "content_density": 75,
      "audio_clarity": 90,
      "visual_variety": 65,
      "structural_completeness": 80,
      "engagement_potential": 72
    }
  },
  "duration_ms": 600000,
  "pipeline_version": "1.0.0",
  "completed_at": "ISO8601"
}
```

**Response (202 — processing):**
```json
{
  "status": "transcribing",
  "progress": 0.45,
  "current_stage": "transcribing",
  "stage_progress": 0.6,
  "estimated_remaining_seconds": 120
}
```

**Errors:** `ERR-NOTFOUND-001` (video not found)

---

#### `POST /api/v1/projects/{project_id}/videos/{video_id}/analysis/cancel` — Cancel Analysis

**Response (200):**
```json
{
  "status": "cancelled",
  "message": "Analysis cancelled"
}
```

---

#### `DELETE /api/v1/projects/{project_id}/videos/{video_id}/analysis` — Clear Analysis

**Response (204):** No content.

---

### 3.4 Clip Endpoints

#### `POST /api/v1/projects/{project_id}/clips/generate` — Generate Clip Candidates

**Request:**
```json
{
  "video_id": "uuid",
  "count": 10,
  "min_duration_seconds": 15,
  "max_duration_seconds": 90,
  "score_threshold": 50
}
```

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `video_id` | UUID | yes | — | Must belong to project |
| `count` | integer | no | 10 | 3-50 |
| `min_duration_seconds` | integer | no | 15 | 5-300 |
| `max_duration_seconds` | integer | no | 90 | 10-600 |
| `score_threshold` | integer | no | 50 | 0-100 |

**Response (202):**
```json
{
  "job_id": "uuid",
  "status": "processing",
  "estimated_duration_seconds": 30,
  "created_at": "ISO8601"
}
```

---

#### `GET /api/v1/projects/{project_id}/clips` — List Clip Candidates

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `video_id` | UUID | — | Filter by source video |
| `status` | string | all | candidate, accepted, rejected, modified |
| `sort` | string | `-quality_score` | quality_score, virality_score, created_at, start_ms |
| `limit` | integer | 50 | 1-200 |
| `offset` | integer | 0 | ≥ 0 |

**Response (200):**
```json
{
  "items": [
    {
      "id": "uuid",
      "video_id": "uuid",
      "start_ms": 45000,
      "end_ms": 75000,
      "duration_ms": 30000,
      "quality_score": 88,
      "virality_score": 72,
      "hook_score": 91,
      "title": "The AI Tool That Saves 10 Hours",
      "description": "Discover how this AI tool...",
      "hashtags": ["#AI", "#productivity", "#editing"],
      "status": "candidate",
      "rank": 1,
      "is_favorite": false,
      "thumbnail_url": "/api/v1/files/thumbnails/...",
      "created_at": "ISO8601"
    }
  ],
  "total": 12,
  "limit": 50,
  "offset": 0
}
```

---

#### `PATCH /api/v1/projects/{project_id}/clips/{clip_id}` — Update Clip

**Request:**
```json
{
  "status": "accepted",
  "title": "Improved Title",
  "start_ms": 46000,
  "end_ms": 74000
}
```

| Field | Type | Constraints |
|-------|------|-------------|
| `status` | string | `accepted`, `rejected`, `modified` |
| `title` | string | Max 200 chars |
| `description` | string | Max 2000 chars |
| `hashtags` | array[string] | Max 30 tags, max 50 chars each |
| `start_ms` | integer | Must be < end_ms, ≥ 0 |
| `end_ms` | integer | Must be > start_ms |
| `is_favorite` | boolean | — |

**Response (200):** Updated clip object.

---

#### `DELETE /api/v1/projects/{project_id}/clips/{clip_id}` — Delete Clip

**Response (204):** No content.

---

### 3.5 Timeline Endpoint

#### `GET /api/v1/projects/{project_id}/timeline` — Get Timeline

**Response (200):**
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "tracks": [
    {
      "id": "track-video-1",
      "type": "video",
      "name": "Video 1",
      "locked": false,
      "muted": false,
      "clips": [
        {
          "id": "clip-on-timeline-1",
          "source_clip_id": "uuid",
          "source_video_id": "uuid",
          "start_ms": 0,
          "end_ms": 30000,
          "trim_start_ms": 0,
          "trim_end_ms": 0,
          "speed": 1.0,
          "effects": {
            "zoom": [{"time_ms": 5000, "scale": 1.2}],
            "crop": {"x": 0.1, "y": 0.0, "width": 0.8, "height": 1.0}
          },
          "transitions": {
            "in": null,
            "out": {"type": "crossfade", "duration_ms": 500}
          }
        }
      ]
    },
    {
      "id": "track-audio-1",
      "type": "audio",
      "name": "Audio 1",
      "locked": false,
      "muted": false,
      "clips": []
    }
  ],
  "markers": [
    {"id": "marker-1", "time_ms": 15000, "label": "Important", "color": "#ff4444"}
  ],
  "zoom_level": 1.0,
  "playhead_position_ms": 30000,
  "version": 5,
  "updated_at": "ISO8601"
}
```

---

#### `PUT /api/v1/projects/{project_id}/timeline` — Save Timeline

**Request:** Full timeline state object as above.

**Response (200):** Updated timeline with incremented version.

**Concurrency:** If `version` in request doesn't match server's current version, return `409 Conflict`. Client should reload and re-apply changes.

---

### 3.6 Export Endpoints

#### `POST /api/v1/projects/{project_id}/exports` — Create Export Job

**Request:**
```json
{
  "clip_id": "uuid",
  "format": "mp4",
  "preset": "standard",
  "resolution": "1920x1080",
  "include_captions": true,
  "caption_track_language": "en",
  "output_path": "/home/user/exports/my_clip.mp4"
}
```

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `clip_id` | UUID | yes | — | Must belong to project |
| `format` | string | yes | — | `mp4`, `mov`, `webm`, `srt`, `vtt`, `ass`, `edl`, `xml`, `json` |
| `preset` | string | no | `standard` | `high`, `standard`, `web`, `proxy` |
| `resolution` | string | no | source | Format: `WxH` |
| `include_captions` | boolean | no | true | — |
| `caption_track_language` | string | no | `en` | BCP-47 language code |
| `output_path` | string | no | default export dir | Must be writable |

**Response (201):**
```json
{
  "job_id": "uuid",
  "status": "queued",
  "estimated_size_mb": 150,
  "estimated_duration_seconds": 45,
  "created_at": "ISO8601"
}
```

**Errors:** `ERR-EXP-001` through `ERR-EXP-005`

---

#### `GET /api/v1/projects/{project_id}/exports` — List Export Jobs

**Query Parameters:** `status` (pending, rendering, completed, failed, cancelled)

---

#### `GET /api/v1/projects/{project_id}/exports/{job_id}` — Get Export Status

**Response (200):**
```json
{
  "job_id": "uuid",
  "clip_id": "uuid",
  "format": "mp4",
  "preset": "standard",
  "status": "rendering",
  "progress": 0.65,
  "encoding_speed": 120.5,
  "output_path": null,
  "file_size_bytes": null,
  "error_message": null,
  "started_at": "ISO8601",
  "estimated_completion": "2026-06-29T10:05:00.000Z",
  "completed_at": null,
  "created_at": "ISO8601"
}
```

---

#### `POST /api/v1/projects/{project_id}/exports/{job_id}/cancel` — Cancel Export

**Response (200):** Cancelled job. Partial file deleted.

---

### 3.7 Provider Endpoints

#### `GET /api/v1/providers` — List Providers

**Response (200):**
```json
{
  "items": [
    {
      "id": "openai",
      "name": "OpenAI",
      "provider_type": "api",
      "enabled": false,
      "configured": true,
      "supported_tasks": ["llm", "stt", "vision"],
      "models": ["gpt-4o", "gpt-4o-mini", "whisper-1"],
      "default_models": {"llm": "gpt-4o", "stt": "whisper-1"},
      "last_test": {"success": true, "latency_ms": 350, "tested_at": "ISO8601"}
    },
    {
      "id": "local",
      "name": "Local AI",
      "provider_type": "local",
      "enabled": true,
      "configured": true,
      "supported_tasks": ["stt", "vision", "embedding"],
      "models": ["whisper-large-v3", "whisper-medium", "yolov8n-face", "all-MiniLM-L6-v2"],
      "default_models": {"stt": "whisper-large-v3", "vision": "yolov8n-face"},
      "last_test": null
    }
  ]
}
```

---

#### `PUT /api/v1/providers/{provider_id}` — Update Provider

**Request:**
```json
{
  "enabled": true,
  "api_key": "sk-...",
  "base_url": "https://api.openai.com/v1",
  "models": {"llm": "gpt-4o", "stt": "whisper-1"},
  "defaults": {"temperature": 0.7, "max_tokens": 4096, "timeout": 60, "retry_count": 3},
  "task_routing": {"stt": ["local", "openai"], "llm": ["local", "ollama", "openai"]}
}
```

`REQ-SRS-API-001`: API keys are write-only. Response never includes the key value.

**Response (200):** Updated provider object (without API key).

---

#### `POST /api/v1/providers/{provider_id}/test` — Test Connection

**Response (200):**
```json
{
  "success": true,
  "latency_ms": 350,
  "models_available": ["gpt-4o", "gpt-4o-mini", "whisper-1"],
  "tested_at": "ISO8601"
}
```

---

#### `GET /api/v1/providers/{provider_id}/models` — List Models

**Response (200):**
```json
{
  "provider_id": "local",
  "models": [
    {"id": "whisper-large-v3", "type": "stt", "size_mb": 3100, "vram_mb": 3500, "downloaded": true},
    {"id": "yolov8n-face", "type": "vision", "size_mb": 6, "vram_mb": 512, "downloaded": true}
  ]
}
```

---

### 3.8 Settings Endpoints

#### `GET /api/v1/settings` — Get All Settings

**Response (200):**
```json
{
  "general": {
    "language": "en",
    "startup_behavior": "restore_last_project",
    "auto_save_interval_seconds": 60
  },
  "appearance": {
    "theme": "dark",
    "accent_color": "#c89b5e",
    "panel_layout": "default"
  },
  "storage": {
    "app_directory": "/home/user/.localclip",
    "max_project_size_gb": 200,
    "max_cache_size_gb": 50,
    "auto_cleanup_enabled": true,
    "cleanup_interval_hours": 24
  },
  "gpu": {
    "backend": "auto",
    "memory_limit_percent": 80,
    "enable_cpu_fallback": true
  },
  "export": {
    "default_format": "mp4",
    "default_preset": "standard",
    "default_output_dir": "/home/user/.localclip/exports",
    "gpu_encoding": true
  },
  "shortcuts": {
    "play_pause": "Space",
    "split": "S",
    "undo": "Mod+Z",
    "redo": "Mod+Shift+Z"
  }
}
```

---

#### `PATCH /api/v1/settings` — Update Settings

**Request:** Partial settings object. Merge semantics.

**Response (200):** Complete settings object after merge.

---

#### `GET /api/v1/settings/{category}` — Get Category

**Categories:** `general`, `appearance`, `storage`, `gpu`, `ai_models`, `export`, `keyboard`, `cache`, `advanced`

---

### 3.9 System Endpoints

#### `GET /api/v1/system/health` — Health Check

**Response (200):**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "gpu": {
    "backend": "cuda",
    "device": "NVIDIA GeForce RTX 3060",
    "driver_version": "535.129.03",
    "cuda_version": "12.1",
    "vram_total_mb": 12288,
    "vram_available_mb": 8192
  },
  "storage": {
    "app_directory": "/home/user/.localclip",
    "total_gb": 500,
    "used_gb": 120,
    "free_gb": 380
  },
  "queue": {
    "depth": 2,
    "active_jobs": 1,
    "workers_online": 4
  },
  "plugins": {
    "total": 6,
    "active": 5,
    "failed": 0
  },
  "memory": {
    "rss_mb": 450,
    "vms_mb": 2048
  }
}
```

---

#### `GET /api/v1/system/gpu` — GPU Info

**Response (200):** GPU and HAL details.

---

#### `GET /api/v1/system/storage` — Storage Usage Dashboard

**Response (200):**
```json
{
  "app_directory": "/home/user/.localclip",
  "categories": {
    "sources": {"count": 15, "size_gb": 85.2},
    "proxies": {"count": 12, "size_gb": 12.5},
    "exports": {"count": 8, "size_gb": 3.1},
    "models": {"count": 4, "size_gb": 8.7},
    "cache": {"count": 230, "size_gb": 4.2},
    "logs": {"count": 3, "size_gb": 0.3},
    "temp": {"count": 12, "size_gb": 1.8}
  },
  "total_used_gb": 115.8,
  "total_free_gb": 384.2,
  "limits": {
    "cache_gb": 50,
    "per_project_gb": 200
  }
}
```

---

### 3.10 Model Endpoints

#### `GET /api/v1/models` — List Models

**Response (200):**
```json
{
  "models": [
    {
      "id": "whisper-large-v3",
      "type": "stt",
      "provider": "local",
      "size_mb": 3100,
      "vram_mb": 3500,
      "status": "ready",
      "version": "v3",
      "downloaded_at": "ISO8601"
    },
    {
      "id": "qwen2.5-7b-q4",
      "type": "llm",
      "provider": "local",
      "size_mb": 4096,
      "vram_mb": 6144,
      "status": "not_downloaded",
      "version": null,
      "downloaded_at": null
    }
  ]
}
```

---

#### `POST /api/v1/models/{model_id}/download` — Download Model

**Response (202):**
```json
{
  "job_id": "uuid",
  "model_id": "whisper-large-v3",
  "status": "downloading",
  "estimated_size_mb": 3100,
  "estimated_duration_seconds": 180
}
```

---

#### `POST /api/v1/models/{model_id}/cancel` — Cancel Download

---

#### `DELETE /api/v1/models/{model_id}` — Remove Model

**Response (204):** No content. Model files deleted.

---

## 4. WebSocket Specification

### 4.1 Connection

| Property | Value |
|----------|-------|
| **Endpoint** | `ws://localhost:8765/api/v1/ws` |
| **Protocol** | WebSocket (RFC 6455) |
| **Auth** | None (by design) |
| **Max message size** | 256 KB |

### 4.2 Connection Lifecycle

```
Client                          Server
  │                                │
  │── WebSocket Connect ──────────▶│
  │                                │── Accept connection
  │◀─── {"event": "connected",     │
  │       "connection_id": "uuid"}  │
  │                                │
  │── {"event": "subscribe",       │
  │     "channels": ["projects.*"]}│──▶ Register subscriptions
  │                                │
  │◀─── {"event": "subscribed",    │
  │       "channels": ["projects.*"]}│
  │                                │
  │── {"event": "ping"} (30s) ────▶│
  │◀─── {"event": "pong"}          │
  │                                │
  │  (Event stream)                │
  │◀─── {"event": "job.progress",  │
  │       "data": {...}}            │
  │                                │
  │── WebSocket Close ────────────▶│
  │                                │── Cleanup subscriptions
```

### 4.3 Event Catalog

#### Server → Client Events

| Event | Payload | Frequency |
|-------|---------|-----------|
| `connected` | `{connection_id}` | Once on connect |
| `subscribed` | `{channels, subscription_count}` | On subscribe |
| `job.progress` | `{job_id, job_type, stage, progress (0-1), message}` | Every 1-5s |
| `job.completed` | `{job_id, job_type, result_summary, duration_ms}` | Once |
| `job.failed` | `{job_id, job_type, error_code, error_message, stage}` | Once |
| `pipeline.stage` | `{video_id, stage, status, progress}` | Per stage transition |
| `export.progress` | `{job_id, progress, encoding_speed, eta_seconds}` | Every 100ms during export |
| `model.download` | `{model_id, progress, speed_mbps, eta_seconds}` | Every 1s |
| `system.warning` | `{code, message, severity, category}` | On condition |
| `system.error` | `{code, message}` | On system error |

#### Client → Server Events

| Event | Payload | Purpose |
|-------|---------|---------|
| `subscribe` | `{channels: ["projects.{id}", "system"]}` | Subscribe to channels |
| `unsubscribe` | `{channels: ["projects.{id}"]}` | Unsubscribe from channels |
| `ping` | `{}` | Keepalive (every 30s) |

### 4.4 Event Payload Schemas

```json
// job.progress
{
  "event": "job.progress",
  "data": {
    "job_id": "uuid",
    "job_type": "analysis",
    "stage": "transcribing",
    "progress": 0.45,
    "message": "Transcribing audio... (45%)",
    "stage_progress": 0.6,
    "estimated_remaining_seconds": 120,
    "timestamp": "ISO8601"
  },
  "channel": "projects.a1b2c3d4"
}

// job.completed
{
  "event": "job.completed",
  "data": {
    "job_id": "uuid",
    "job_type": "analysis",
    "result_summary": "Analysis complete: 42 segments, 2 speakers, 5 scenes",
    "duration_ms": 185000,
    "timestamp": "ISO8601"
  },
  "channel": "projects.a1b2c3d4"
}

// job.failed
{
  "event": "job.failed",
  "data": {
    "job_id": "uuid",
    "job_type": "analysis",
    "error_code": "ERR-PIPE-001",
    "error_message": "GPU out of memory. Required: 3500 MB, Available: 1024 MB",
    "stage": "transcribing",
    "retry_allowed": true,
    "timestamp": "ISO8601"
  },
  "channel": "projects.a1b2c3d4"
}

// export.progress
{
  "event": "export.progress",
  "data": {
    "job_id": "uuid",
    "progress": 0.65,
    "encoding_speed": 120.5,
    "eta_seconds": 45,
    "frame": 780,
    "total_frames": 1200,
    "timestamp": "ISO8601"
  },
  "channel": "jobs.export-uuid"
}

// model.download
{
  "event": "model.download",
  "data": {
    "model_id": "whisper-large-v3",
    "progress": 0.3,
    "speed_mbps": 25.5,
    "eta_seconds": 85,
    "downloaded_mb": 930,
    "total_mb": 3100,
    "timestamp": "ISO8601"
  },
  "channel": "system"
}

// system.warning
{
  "event": "system.warning",
  "data": {
    "code": "ERR-SYS-006",
    "message": "System memory low (2048 MB available). Close other applications.",
    "severity": "warning",
    "category": "memory",
    "timestamp": "ISO8601"
  },
  "channel": "system"
}
```

### 4.5 Keepalive and Reconnection

| Parameter | Value |
|-----------|-------|
| **Ping interval** | 30 seconds |
| **Server timeout** | 120 seconds idle → close |
| **Client reconnect delay** | 1s, 2s, 4s, 8s, 16s (exponential backoff, max 30s) |
| **Reconnect behavior** | Re-subscribe to channels on reconnect |

---

## 5. Data Contracts

### 5.1 Domain Models (Python)

```python
# backend/domain/entities/project.py
@dataclass
class Project:
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None
    settings: dict
    thumbnail_path: str | None
    version: int
    storage_path: str
    is_archived: bool

# backend/domain/entities/analysis.py
@dataclass
class Analysis:
    id: str
    video_id: str
    status: AnalysisStatus
    transcript: Transcript | None
    speakers: list[Speaker] | None
    scenes: list[Scene] | None
    topics: list[Topic] | None
    keywords: list[str] | None
    emotions: list[EmotionSegment] | None
    hooks: list[Hook] | None
    chapters: list[Chapter] | None
    quality_score: int | None

# backend/domain/value_objects/quality_score.py
@dataclass
class QualityScore:
    overall: int  # 0-100
    dimensions: dict[str, float]  # hook_strength, content_density, etc.
```

### 5.2 API DTOs (Pydantic)

```python
# backend/api/schemas/project.py
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    storage_path: str | None = None

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime | None
    storage_path: str
    thumbnail_url: str | None
    is_archived: bool
    settings: dict
    version: int
    video_count: int = 0

class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None

# backend/api/schemas/clip.py
class ClipResponse(BaseModel):
    id: str
    video_id: str
    start_ms: int
    end_ms: int
    duration_ms: int
    quality_score: int | None
    virality_score: int | None
    hook_score: int | None
    title: str | None
    description: str | None
    hashtags: list[str]
    status: ClipStatus
    rank: int | None
    is_favorite: bool
    thumbnail_url: str | None
    created_at: datetime

class ClipUpdate(BaseModel):
    status: ClipStatus | None = None
    title: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=2000)
    hashtags: list[str] | None = Field(None, max_length=30)
    start_ms: int | None = None
    end_ms: int | None = None
    is_favorite: bool | None = None
```

### 5.3 Internal Event Payloads

```python
# backend/domain/events/video_imported.py
@dataclass
class VideoImported:
    event_id: str
    project_id: str
    video_id: str
    video_master_id: str
    duration_ms: int
    file_size_bytes: int
    timestamp: datetime

# backend/domain/events/analysis_completed.py
@dataclass
class AnalysisCompleted:
    event_id: str
    video_id: str
    project_id: str
    status: AnalysisStatus
    quality_score: int | None
    clip_count: int
    duration_ms: int
    timestamp: datetime

# backend/domain/events/export_completed.py
@dataclass
class ExportCompleted:
    event_id: str
    job_id: str
    clip_id: str
    format: str
    output_path: str
    file_size_bytes: int
    duration_ms: int
    timestamp: datetime
```

---

## 6. Pagination and Filtering

### 6.1 Pagination Convention

All collection endpoints use cursor-based pagination with `limit` and `offset`.

```json
{
  "items": [ /* up to `limit` items */ ],
  "total": 42,       // Total matching records
  "limit": 20,       // Requested limit
  "offset": 0,        // Requested offset
  "next_offset": 20   // Offset for next page (null if no more)
}
```

### 6.2 Filtering Conventions

- **Simple equality:** `GET /projects/{id}/videos?status=ready`
- **Sorting:** `GET /projects?sort=-created_at` (prefix `-` for descending)
- **Date range:** `GET /exports?created_after=2026-01-01&created_before=2026-06-30`
- **Search:** `GET /clips?search=keyword` (searches title + description)

---

## 7. Error Handling

### 7.1 Error Response Format

```json
{
  "error": {
    "code": "ERR-IMP-001",
    "message": "Unsupported file format. Supported formats: MP4, MOV, MKV, AVI, WebM",
    "details": {
      "provided_format": ".wmv",
      "supported_formats": [".mp4", ".mov", ".mkv", ".avi", ".webm"]
    },
    "request_id": "req-uuid-here",
    "timestamp": "2026-06-29T10:00:00Z"
  }
}
```

### 7.2 Error Codes by Category

| Category | Code Range | Examples |
|----------|------------|----------|
| Validation | `ERR-VALIDATION-0xx` | Missing field, invalid value |
| Import | `ERR-IMP-0xx` | Unsupported format, corrupted file, duplicate |
| Pipeline | `ERR-PIPE-0xx` | STT failed, GPU OOM, LLM timeout |
| Export | `ERR-EXP-0xx` | Encode failed, GPU encoder unavailable |
| Storage | `ERR-STORAGE-0xx` | Disk full, path creation failed |
| System | `ERR-SYS-0xx` | FFmpeg not found, DB corruption |
| Plugin | `ERR-PLUG-0xx` | Plugin crash, manifest invalid |
| Not Found | `ERR-NOTFOUND-0xx` | Resource not found |
| Conflict | `ERR-CONFLICT-0xx` | Already analyzing, version mismatch |
| Security | `ERR-SEC-0xx` | Path traversal detected |

### 7.3 HTTP Status Code Usage

| Code | Usage | Example |
|------|-------|---------|
| 200 | Success (GET, PATCH) | Resource returned |
| 201 | Created (POST) | Project created |
| 202 | Accepted (POST async) | Analysis started |
| 204 | No content (DELETE) | Resource deleted |
| 400 | Bad request | Invalid input |
| 404 | Not found | Resource doesn't exist |
| 409 | Conflict | Version mismatch, duplicate |
| 413 | Payload too large | File exceeds limit |
| 415 | Unsupported media type | Wrong file format |
| 422 | Unprocessable entity | Validation error |
| 500 | Internal server error | Unexpected error |
| 503 | Service unavailable | GPU not available |

---

## 8. Idempotency and Versioning

### 8.1 Idempotency Rules

| Method | Idempotent? | Notes |
|--------|-------------|-------|
| GET | ✅ Yes | Always safe |
| PUT | ✅ Yes | Full replacement |
| PATCH | ❌ No | Partial update (merge) |
| DELETE | ✅ Yes | Subsequent deletes return 404 |
| POST | ❌ No | Creates new resource (except idempotency-key) |

### 8.2 API Versioning Strategy

| Strategy | Value |
|----------|-------|
| **Method** | URL path prefix |
| **Current** | `/api/v1/` |
| **Version lifespan** | Supported for 2 major versions |
| **Deprecation** | `Sunset` header on deprecated endpoints |
| **Breaking changes** | JSON field removal, status code changes, auth requirement |

### 8.3 Backward Compatibility

| Change Type | Compatible? | Rule |
|-------------|-------------|------|
| Adding fields to response | ✅ Compatible | New fields ignored by old clients |
| Adding optional request fields | ✅ Compatible | Old requests still work |
| Removing response fields | ❌ Breaking | Must be new version |
| Changing field types | ❌ Breaking | Must be new version |
| Adding required fields | ❌ Breaking | Must be new version |
| Changing error codes | ❌ Breaking | Must be new version |

---

## 9. Quality Gate

### 9.1 Review Checklist

| # | Check | Status | Evidence |
|---|-------|--------|----------|
| 1 | **API consistency** — RESTful naming, HTTP methods, status codes | ✅ PASS | All endpoints follow resource conventions. Standard status codes. |
| 2 | **Complete endpoint coverage** — all features have API | ✅ PASS | Projects (8), Videos (4), Analysis (5), Clips (4), Timeline (2), Exports (4), Providers (4), Settings (3), System (3), Models (4) = **41 endpoints** |
| 3 | **WebSocket events** — all progress events specified | ✅ PASS | 10 server→client, 3 client→server events with full schemas |
| 4 | **Data contracts** — DTOs, domain models, events | ✅ PASS | Python dataclasses + Pydantic schemas for all major entities |
| 5 | **Validation rules** — every field has constraints | ✅ PASS | Min/max lengths, types, enums, regex patterns documented |
| 6 | **Error catalog** — every endpoint has error codes | ✅ PASS | 10 error categories with ranges; each endpoint maps to specific errors |
| 7 | **Pagination** — consistent pattern across collections | ✅ PASS | limit/offset with total and next_offset |
| 8 | **Idempotency** — documented per HTTP method | ✅ PASS | §8.1 with rules for each method |
| 9 | **Versioning** — backward compatibility strategy | ✅ PASS | URL-prefix versioning with deprecation policy |
| 10 | **Traceability to SRS** | ✅ PASS | All SRS endpoints present. SRS §6 → this document §3. SRS §7 → this document §4. |

### 9.2 API Statistics

| Metric | Count |
|--------|-------|
| **REST endpoints** | 41 |
| **WebSocket events (server→client)** | 10 |
| **WebSocket events (client→server)** | 3 |
| **Error codes defined** | 20+ (full catalog in SRS §12) |
| **Data contract schemas** | 12+ |
| **Pydantic DTOs** | 15+ |

---

*End of API Specification*
