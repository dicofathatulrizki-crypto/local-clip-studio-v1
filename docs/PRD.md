# Local Clip Studio — Product Requirements Document

> **Status:** DRAFT  
> **Version:** 1.0  
> **Date:** 2026-06-29  
> **Traceability:** Vision Document v2.0 (Approved)

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Feature Requirements](#2-feature-requirements)
   - [F-01: Video Import](#f-01-video-import)
   - [F-02: AI Analysis Pipeline](#f-02-ai-analysis-pipeline)
   - [F-03: AI Clip Generation](#f-03-ai-clip-generation)
   - [F-04: Timeline Editor](#f-04-timeline-editor)
   - [F-05: AI Smart Reframe](#f-05-ai-smart-reframe)
   - [F-06: Auto Zoom](#f-06-auto-zoom)
   - [F-07: Captions](#f-07-captions)
   - [F-08: Translation](#f-08-translation)
   - [F-09: AI Voice Processing](#f-09-ai-voice-processing)
   - [F-10: AI Visual Generation](#f-10-ai-visual-generation)
   - [F-11: AI Content Generation](#f-11-ai-content-generation)
   - [F-12: AI Assistants](#f-12-ai-assistants)
   - [F-13: Export](#f-13-export)
   - [F-14: Batch Processing](#f-14-batch-processing)
   - [F-15: Project Management](#f-15-project-management)
   - [F-16: AI Provider Management](#f-16-ai-provider-management)
   - [F-17: Plugin System](#f-17-plugin-system)
   - [F-18: Processing Analytics](#f-18-processing-analytics)
   - [F-19: UI & Workspace](#f-19-ui--workspace)
   - [F-20: Performance & Acceleration](#f-20-performance--acceleration)
   - [F-21: Settings](#f-21-settings)
   - [F-22: Storage Management](#f-22-storage-management)
3. [Non-Functional Requirements](#3-non-functional-requirements)
4. [Glossary](#4-glossary)

---

## 1. Introduction

### 1.1 Purpose

This Product Requirements Document defines the complete feature set for Local Clip Studio — a local-first, AI-powered video editing application that transforms long-form videos into short-form vertical clips. This document translates the approved Vision Document into actionable product requirements for engineering teams.

### 1.2 Scope

The application targets a single user on a single machine. All processing is local. The browser serves as the UI layer only. All features defined herein are in-scope for v1.0, organized into implementation milestones.

### 1.3 Requirement ID Format

Each requirement is uniquely identified as: `PRD-{Domain}-{NNN}`

Priorities:
- **P0 (Must)** — Critical for MVP; blocks other features
- **P1 (Should)** — Important but not blocking
- **P2 (Could)** — Nice to have, included in architecture but deferrable

### 1.4 Traceability Key

Each requirement traces to the Vision Document section(s) that mandate it.

---

## 2. Feature Requirements

---

### F-01: Video Import

#### Overview
Import video files into the application for processing. Supports local file import, drag-and-drop, YouTube URLs, batch operations, and folder import.

#### User Stories

| ID | Story |
|----|-------|
| US-F01-001 | As a user, I want to import a video file from my local filesystem so I can start editing. |
| US-F01-002 | As a user, I want to drag and drop video files into the application to quickly import them. |
| US-F01-003 | As a user, I want to import videos from a YouTube URL so I can clip online content. |
| US-F01-004 | As a user, I want to batch-import multiple video files at once. |
| US-F01-005 | As a user, I want to import an entire folder of videos. |
| US-F01-006 | As a user, I want to preview video metadata (resolution, duration, codec, file size) before importing. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-IMP-001 | Application shall support importing MP4, MOV, MKV, AVI, WebM file formats | P0 | §4 Feature Scope |
| PRD-IMP-002 | Application shall validate file extension and attempt to probe the file with FFmpeg before accepting it | P0 | §8 Security |
| PRD-IMP-003 | Application shall reject files exceeding the configured maximum import size (default: 50GB) with a clear error message | P0 | §8 Security |
| PRD-IMP-004 | Application shall support single-file selection via native OS file picker | P0 | §4 Feature Scope |
| PRD-IMP-005 | Application shall support drag-and-drop from OS file manager into the import area | P0 | §4 Feature Scope |
| PRD-IMP-006 | Application shall extract and display metadata: filename, resolution, duration, codec, file size, frame rate, bitrate | P1 | §4 Feature Scope |
| PRD-IMP-007 | Application shall support YouTube URL import via yt-dlp integration | P1 | §4 Feature Scope |
| PRD-IMP-008 | Application shall support batch import of multiple files simultaneously | P1 | §4 Feature Scope |
| PRD-IMP-009 | Application shall support recursive folder import | P2 | §4 Feature Scope |
| PRD-IMP-010 | Application shall copy imported files into the project's source directory to ensure immutability | P0 | §3.8 Storage |
| PRD-IMP-011 | Application shall generate a SHA-256 hash of each imported file for deduplication | P1 | §3.8 Storage |

#### Acceptance Criteria

- AC-F01-001: Importing a valid MP4 file results in the file appearing in the project's media panel within 2 seconds (for a 1GB file)
- AC-F01-002: Dragging a MOV file onto the app copies it to the project directory and shows metadata
- AC-F01-003: Attempting to import a corrupted file shows a descriptive error: "File appears to be corrupted or unreadable: [path]"
- AC-F01-004: YouTube URL import downloads the best available quality and shows progress
- AC-F01-005: Importing the same file twice (same SHA-256) shows: "This file has already been imported"

#### Edge Cases

- File is locked by another process → show error with unlock instructions
- File has unusual codec → transcode to supported format during import
- YouTube URL is private/deleted → clear error message
- Disk space insufficient → show required vs. available space, offer cleanup
- File name contains special characters → sanitize filename on copy
- Very long file names (>255 chars) → truncate with hash suffix

#### Data Flow

```
User Action → File Picker / Drop Zone / URL Input
    │
    ▼
Validation Layer
    ├── File extension check
    ├── FFprobe probe
    ├── Size limit check
    ├── Disk space check
    └── Duplicate check (SHA-256)
    │
    ▼
Import Handler
    ├── Copy to source directory
    ├── Generate proxy (optional)
    ├── Extract metadata
    └── Register in database
    │
    ▼
Media Panel ← API Response
```

#### Error Handling

| Scenario | Error Message | Recovery |
|----------|---------------|----------|
| Unsupported format | "Unsupported file format. Supported: MP4, MOV, MKV, AVI, WebM" | User selects different file |
| Corrupted file | "Cannot read file metadata. The file may be corrupted." | User verifies source file |
| Disk full | "Insufficient disk space. Need X GB, have Y GB available." | User frees space or changes storage location |
| Download failure | "YouTube download failed: [reason]" | User checks URL or internet connection |

#### Performance Targets

| Metric | Target |
|--------|--------|
| File validation | < 1 second for files up to 10GB |
| Metadata extraction | < 2 seconds |
| File copy (1GB file to NVMe SSD) | < 10 seconds |
| YouTube download progress updates | Every 5% or 10 seconds |
| Batch import throughput | 4 files/minute (for 1GB files on NVMe) |

#### Storage Requirements

| Item | Path | Retention |
|------|------|-----------|
| Source video | `{project_dir}/sources/{hash}.{ext}` | Until project deleted |
| Import temp | `{app_dir}/temp/import/` | Deleted after import |

#### Testing Considerations

- Test with all supported formats
- Test with corrupted/invalid files
- Test with very large files (close to limit)
- Test concurrent batch imports
- Test disk-full scenario
- Test YouTube URL edge cases (private, deleted, age-restricted)

---

### F-02: AI Analysis Pipeline

#### Overview
Automated analysis of imported videos through a multi-stage AI pipeline: speech-to-text, speaker diarization, scene detection, silence detection, topic segmentation, semantic understanding, hook detection, virality scoring, and quality scoring.

#### User Stories

| ID | Story |
|----|-------|
| US-F02-001 | As a user, I want the application to automatically transcribe my video with word-level timestamps. |
| US-F02-002 | As a user, I want the application to identify different speakers in the video. |
| US-F02-003 | As a user, I want the application to detect scene changes automatically. |
| US-F02-004 | As a user, I want the application to detect silent sections in my video. |
| US-F02-005 | As a user, I want the application to identify the most engaging/hooky moments in my video. |
| US-F02-006 | As a user, I want a quality score for each potential clip explaining why it's scored that way. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-AIP-001 | Pipeline shall run speech-to-text using the configured STT provider (default: WhisperX) | P0 | §3.4, §5 |
| PRD-AIP-002 | Pipeline shall produce word-level timestamps with confidence scores | P0 | §5 |
| PRD-AIP-003 | Pipeline shall perform speaker diarization to label who spoke when | P1 | §5 |
| PRD-AIP-004 | Pipeline shall detect scene changes using histogram and content analysis (PySceneDetect) | P0 | §5 |
| PRD-AIP-005 | Pipeline shall detect silent sections (configurable threshold: default -30dB for 0.5s) | P1 | §5 |
| PRD-AIP-006 | Pipeline shall segment transcript into topics using LLM or embedding similarity | P1 | §5 |
| PRD-AIP-007 | Pipeline shall analyze transcript semantically to extract key themes, entities, and claims | P2 | §5 |
| PRD-AIP-008 | Pipeline shall identify potential hooks — moments with high engagement signals | P1 | §5 |
| PRD-AIP-009 | Pipeline shall calculate a virality score (0-100) per segment | P1 | §6 |
| PRD-AIP-010 | Pipeline shall calculate a quality score (0-100) per clip candidate | P0 | §6 |
| PRD-AIP-011 | Pipeline shall detect emotional tone per segment (positive, negative, neutral, excitement, etc.) | P2 | §5 |
| PRD-AIP-012 | Pipeline shall extract keywords and key phrases from transcript | P1 | §5 |
| PRD-AIP-013 | Pipeline shall generate chapter markers from topic segmentation | P2 | §5 |
| PRD-AIP-014 | Pipeline execution shall be asynchronous with progress reporting via WebSocket | P0 | §3.3 |
| PRD-AIP-015 | Pipeline shall support cancellation mid-execution | P1 | §3.3 |
| PRD-AIP-016 | Pipeline shall support resumption from last completed stage on restart | P2 | §3.3 |
| PRD-AIP-017 | Each pipeline stage shall be independently configurable (enabled/disabled) | P0 | §3.6 |
| PRD-AIP-018 | Each pipeline stage shall have a timeout (configurable, default: 30 minutes) | P1 | §3.3 |
| PRD-AIP-019 | Pipeline shall log structured events with correlation IDs for every stage | P0 | §8 |

#### Acceptance Criteria

- AC-AIP-001: Processing a 10-minute video produces full transcript with < 5% WER
- AC-AIP-002: Scene detection identifies > 90% of actual scene changes with < 10% false positives
- AC-AIP-003: Speaker diarization correctly assigns > 80% of utterances to the correct speaker (2-speaker video)
- AC-AIP-004: Quality score is consistent (+/- 5 points) across repeated runs on the same video
- AC-AIP-005: Pipeline cancellation stops all running stages within 5 seconds
- AC-AIP-006: Progress updates are delivered via WebSocket at least every 2 seconds during active processing

#### Edge Cases

- Video has no speech (music only) → STT returns empty transcript, pipeline continues with visual-only
- Video has multiple languages → auto-detect and process each language segment separately
- Single speaker throughout → diarization returns single speaker label
- Rapid scene changes (e.g., montage) → merge adjacent scenes below minimum threshold (default: 1 second)
- Very long video (>4 hours) → warn user about processing time, suggest proxy editing

#### Data Flow

```
User starts analysis → API endpoint
    │
    ▼
Queue job in Celery
    │
    ▼
Stage 1: FFmpeg Preprocessing
    ├── Audio extraction (16kHz mono WAV)
    ├── Frame extraction (1fps for scene detection)
    └── Proxy generation (720p for timeline)
    │
    ▼
Stage 2: Speech Recognition
    ├── WhisperX transcription
    ├── Word-level timestamps
    └── Language detection
    │
    ▼
Stage 3: Speaker Diarization
    ├── PyAnnote / WhisperX diarization
    └── Speaker label assignment
    │
    ▼
Stage 4: Visual Analysis
    ├── PySceneDetect scene detection
    ├── Face detection / tracking (YOLO)
    └── Silence detection (FFmpeg silencedetect)
    │
    ▼
Stage 5: Semantic Analysis (LLM call)
    ├── Topic segmentation
    ├── Hook detection
    ├── Keywords extraction
    └── Chapter generation
    │
    ▼
Stage 6: Scoring Engine
    ├── Quality score calculation
    ├── Virality score calculation
    └── Clip candidate extraction
    │
    ▼
Results stored → Real-time UI update via WebSocket
```

#### Error Handling

| Scenario | Error Message | Recovery |
|----------|---------------|----------|
| STT model not downloaded | "Whisper model not found. Download now? (X GB required)" | Auto-download or cancel |
| GPU out of memory | "GPU out of memory. Try a smaller model or enable CPU fallback." | Auto-fallback to CPU or smaller model |
| Pipeline stage timeout | "Stage [name] timed out after [N] minutes." | Retry stage or skip |
| LLM provider unavailable | "LLM provider unreachable. Check provider settings." | Fallback to next provider or skip LLM stage |
| No audio track found | "No audio track detected. Speech recognition will be skipped." | Continue with visual-only analysis |

#### Performance Targets

| Metric | Target |
|--------|--------|
| 10-min video total pipeline (RTX 3060) | < 5 minutes |
| WhisperX transcription (1 hour audio) | < 10 minutes (CUDA) |
| Scene detection (1 hour video) | < 2 minutes |
| Speaker diarization (1 hour) | < 5 minutes |
| LLM semantic analysis (1 hour transcript) | < 1 minute (local Qwen 7B) |
| Quality scoring | < 30 seconds |

#### AI Requirements

| Stage | Default Model | Provider Plugin | Fallback |
|-------|--------------|----------------|----------|
| STT | WhisperX large-v3 | whisperx-plugin | Whisper-tiny (CPU) |
| Diarization | PyAnnote 3.1 | diarization-plugin | Speaker labels from STT |
| Scene Detection | PySceneDetect content | scene-plugin | FFmpeg scene detection |
| Face Detection | YOLOv8n-face | vision-plugin | OpenCV Haar cascade |
| Semantic Analysis | Qwen 2.5 7B (llama.cpp) | llm-plugin | Skip if no LLM |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | embedding-plugin | Skip |

#### Testing Considerations

- Test with music-only, speech-only, mixed audio
- Test with single speaker, multiple speakers (2-6)
- Test with fast-paced editing, slow content
- Test pipeline cancellation at every stage
- Test GPU OOM recovery
- Test provider fallback chain

---

### F-03: AI Clip Generation

#### Overview
Automatically generate short-form clip candidates from analyzed video. Includes smart trimming, candidate ranking, duplicate removal, merging of overlapping clips, and auto-generation of title, description, and hashtags.

#### User Stories

| ID | Story |
|----|-------|
| US-F03-001 | As a user, I want the application to automatically suggest the best clips from my video. |
| US-F03-002 | As a user, I want to see multiple clip candidates ranked by quality. |
| US-F03-003 | As a user, I want clips to be intelligently trimmed to remove dead space. |
| US-F03-004 | As a user, I want the application to auto-generate a title and description for each clip. |
| US-F03-005 | As a user, I want to be able to merge overlapping clip candidates. |
| US-F03-006 | As a user, I want duplicate clips to be automatically removed. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-CLIP-001 | System shall extract clip candidates based on hook detection, scene boundaries, and quality scores | P0 | §5 |
| PRD-CLIP-002 | System shall generate minimum 3 and maximum 20 clip candidates per hour of source video | P0 | §4 |
| PRD-CLIP-003 | Each clip candidate shall have a quality score (0-100) with breakdown | P0 | §6 |
| PRD-CLIP-004 | Clip candidates shall be ranked by quality score in the UI | P0 | §4 |
| PRD-CLIP-005 | System shall auto-trim silence (configurable: >0.5s silence) from the start and end of each clip | P0 | §4 |
| PRD-CLIP-006 | System shall detect and remove near-identical clip candidates (cosine similarity > 0.95 on transcript) | P1 | §4 |
| PRD-CLIP-007 | System shall merge overlapping clip candidates by extending to cover the combined range | P1 | §4 |
| PRD-CLIP-008 | System shall auto-generate a title for each clip based on transcript content | P2 | §4 |
| PRD-CLIP-009 | System shall auto-generate a description (1-3 sentences) for each clip | P2 | §4 |
| PRD-CLIP-010 | System shall auto-generate 3-10 hashtags per clip | P2 | §4 |
| PRD-CLIP-011 | Clip candidate duration shall be configurable (default: 15-60 seconds) | P0 | §4 |
| PRD-CLIP-012 | User shall be able to accept, reject, or modify any clip candidate | P0 | §4 |
| PRD-CLIP-013 | User shall be able to manually create clip candidates by selecting start/end times | P0 | §4 |

#### Acceptance Criteria

- AC-CLIP-001: Processing a 30-minute video produces at least 5 clip candidates
- AC-CLIP-002: Ranked list matches manual expert ranking with ≥ 70% overlap in top 3
- AC-CLIP-003: Auto-trim removes ≥ 95% of leading/trailing silence without cutting speech
- AC-CLIP-004: Duplicate removal never removes more than one of two semantically different clips discussing the same topic
- AC-CLIP-005: Auto-titles are descriptive and grammatically correct ≥ 80% of the time

#### Edge Cases

- Video has no clear hooks → generate clips based on scene boundaries only with reduced confidence
- All clips score below threshold → inform user and suggest manual clip creation
- Clip candidates heavily overlap → merge into longer clips or prioritize highest scoring
- Single scene video → generate multiple clips based on transcript segments instead
- User modifies clip boundaries → scores and metadata recalculate for affected clips only

#### Data Flow

```
Analysis Results → Clip Generation Engine
    │
    ▼
Candidate Extraction
    ├── Identify hook moments (score > 70)
    ├── Add context (N seconds before/after hook)
    ├── Snap to scene boundaries
    └── Respect min/max duration limits
    │
    ▼
Candidate Processing
    ├── Trim leading/trailing silence
    ├── Calculate quality score per candidate
    └── Merge overlapping candidates
    │
    ▼
Deduplication
    ├── Transcript similarity comparison
    ├── Scene similarity comparison
    └── Remove near-duplicates
    │
    ▼
Content Generation (LLM)
    ├── Generated title
    ├── Generated description
    └── Generated hashtags
    │
    ▼
Return ranked candidates → UI displays grid of clips
```

#### API Requirements

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/projects/{id}/clips/generate` | POST | Trigger clip generation |
| `/api/v1/projects/{id}/clips` | GET | List clip candidates |
| `/api/v1/projects/{id}/clips/{clip_id}` | PATCH | Update clip (accept, modify, reject) |
| `/api/v1/projects/{id}/clips/{clip_id}` | DELETE | Remove clip candidate |
| `/api/v1/projects/{id}/clips` | POST | Create manual clip |

#### Testing Considerations

- Test with content that has clear vs. unclear hooks
- Test long-form content (2+ hours)
- Test short content (< 2 minutes)
- Test duplicate detection accuracy
- Test merge logic for various overlap scenarios

---

### F-04: Timeline Editor

#### Overview
A desktop-grade timeline editor with multi-track support, waveform visualization, transcript synchronization, split/trim operations, undo/redo, markers, snapping, and keyboard shortcuts.

#### User Stories

| ID | Story |
|----|-------|
| US-F04-001 | As a user, I want a multi-track timeline to arrange my clips and media. |
| US-F04-002 | As a user, I want to see the audio waveform synchronized with the video. |
| US-F04-003 | As a user, I want to split a clip at the playhead position. |
| US-F04-004 | As a user, I want to trim the start or end of a clip. |
| US-F04-005 | As a user, I want to undo/redo any editing action. |
| US-F04-006 | As a user, I want keyboard shortcuts for all common editing operations. |
| US-F04-007 | As a user, I want to use text-based editing — delete words from transcript and have the timeline reflect the edit. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-TL-001 | Timeline shall support multiple video/audio tracks (minimum 3 video + 3 audio) | P0 | §4 |
| PRD-TL-002 | Timeline shall display audio waveform rendered client-side from PCM data | P0 | §4 |
| PRD-TL-003 | Timeline shall support split at playhead position (shortcut: S) | P0 | §4 |
| PRD-TL-004 | Timeline shall support trim from start or end via drag handles | P0 | §4 |
| PRD-TL-005 | Timeline shall support ripple delete (shortcut: Shift+Delete) | P1 | §4 |
| PRD-TL-006 | Timeline shall support move clip to arbitrary position with snapping | P0 | §4 |
| PRD-TL-007 | Timeline shall maintain an undo/redo stack with minimum 100 operations | P0 | §4 |
| PRD-TL-008 | Timeline shall display a cursor/playhead at current playback position | P0 | §4 |
| PRD-TL-009 | Timeline shall support variable zoom levels (frames to minutes) | P1 | §4 |
| PRD-TL-010 | Timeline shall support markers at arbitrary positions (shortcut: M) | P1 | §4 |
| PRD-TL-011 | Timeline shall snap to markers, clip boundaries, playhead, and timeline edges | P1 | §4 |
| PRD-TL-012 | Timeline shall sync with transcript panel — clicking a word seeks to that position | P0 | §5 |
| PRD-TL-013 | Timeline shall support text-based editing — deleting transcript text removes corresponding timeline segment | P1 | §4 |
| PRD-TL-014 | Timeline shall display clip transitions and allow trim of transition handles | P2 | §4 |
| PRD-TL-015 | Timeline shall display proxy video preview in the preview panel | P0 | §4 |
| PRD-TL-016 | Timeline shall support variable playback speed (0.25x, 0.5x, 1x, 1.5x, 2x) | P1 | §4 |
| PRD-TL-017 | Timeline operations shall NOT block the UI (background processing) | P0 | §4 |

#### Acceptance Criteria

- AC-TL-001: Splitting a clip creates two adjacent clips at the playhead position within 100ms
- AC-TL-002: Trimming a clip updates the waveform and preview in real-time (< 50ms latency)
- AC-TL-003: Undo/redo cycles through 100+ operations without state corruption
- AC-TL-004: Waveform renders for a 2-hour audio file within 3 seconds
- AC-TL-005: Clicking a transcript word in the transcript panel seeks the timeline to within 100ms of that word
- AC-TL-006: All keyboard shortcuts work without modifier conflicts

#### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Space / K | Play / Pause |
| J | Play backward |
| L | Play forward |
| ← / → | Step frame backward/forward |
| Shift + ← / → | Step 5 frames |
| I | Set in point |
| O | Set out point |
| S | Split clip |
| Delete | Delete selected clip |
| Shift + Delete | Ripple delete |
| Ctrl+Z / Cmd+Z | Undo |
| Ctrl+Shift+Z / Cmd+Shift+Z | Redo |
| M | Add marker |
| + / - | Zoom in/out timeline |
| Home | Go to timeline start |
| End | Go to timeline end |

#### Data Flow

```
User Interaction → Timeline Component
    │
    ▼
Redux/Zustand Action
    ├── Update timeline state optimistically
    └── Queue server sync (debounced, 1s)
    │
    ▼
Preview Video Element
    ├── Seek to cursor position
    ├── Playback controls
    └── Proxy video source
    │
    ▼
Waveform Canvas
    ├── Audio PCM data (pre-fetched)
    ├── Zoom-aware LOD
    └── Canvas rendering at 60fps
    │
    ▼
Server Sync (debounced)
    └── PATCH /api/v1/projects/{id}/timeline
```

#### UI Requirements

- Timeline minimum height: 200px, expandable to 70% of viewport
- Waveform colors: Dynamic based on selection state (selected: accent, unselected: muted)
- Clip thumbnails: Extracted keyframes shown on clips
- Time ruler: Precise to frame level at max zoom, scene markers shown
- Scrollable horizontally and vertically
- Drag-to-select multiple clips

#### Dependencies

- Web Audio API for waveform rendering (or Canvas-based)
- FFmpeg for proxy generation
- MediaSource Extensions for streaming proxy video

#### Testing Considerations

- Test with 50+ clips on timeline
- Test undo/redo with complex operations
- Test waveform rendering performance
- Test keyboard shortcut conflicts
- Test text-based editing with multi-speaker transcripts

---

### F-05: AI Smart Reframe

#### Overview
Automatically crop horizontal videos into vertical (9:16), square (1:1), or portrait (4:5) aspect ratios. Uses face tracking, speaker tracking, and object tracking to keep the subject in frame.

#### User Stories

| ID | Story |
|----|-------|
| US-F05-001 | As a user, I want to convert a horizontal video to vertical format for TikTok/Reels/Shorts. |
| US-F05-002 | As a user, I want the reframe to track the speaker's face and keep it centered. |
| US-F05-003 | As a user, I want to choose between manual crop and AI reframe. |
| US-F05-004 | As a user, I want to preview the reframed result before rendering. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-RFR-001 | Reframe shall support output aspect ratios: 9:16 (vertical), 1:1 (square), 4:5 (portrait) | P0 | §4 |
| PRD-RFR-002 | Reframe shall use face detection + tracking to keep faces centered (YOLOv8-face) | P0 | §5 |
| PRD-RFR-003 | Reframe shall fall back to speaker tracking when face is not visible | P1 | §4 |
| PRD-RFR-004 | Reframe shall support object tracking for non-human content (SAM) | P2 | §4 |
| PRD-RFR-005 | Reframe shall support multi-person framing — keep all visible speakers in frame | P1 | §4 |
| PRD-RFR-006 | Reframe shall apply smooth camera movement (pan/zoom) between keyframes | P0 | §4 |
| PRD-RFR-007 | Reframe shall allow manual override of tracking keyframes | P0 | §4 |
| PRD-RFR-008 | Reframe results shall be previewable in real-time without full render | P1 | §4 |
| PRD-RFR-009 | Reframe shall process as part of the AI pipeline and store reframe metadata separately from source | P0 | §5 |
| PRD-RFR-010 | Reframe shall interpolate smooth camera motion between tracked keyframes | P1 | §4 |

#### Acceptance Criteria

- AC-RFR-001: Reframing a 10-minute horizontal video to 9:16 keeps the primary speaker centered ≥ 95% of the time
- AC-RFR-002: Face tracking recovers within 2 seconds after occlusion or rapid movement
- AC-RFR-003: Multi-person framing keeps both speakers visible when both are speaking
- AC-RFR-004: Smooth camera motion has no abrupt jumps (position change < 10% of frame width per frame)
- AC-RFR-005: Reframe metadata generation completes within 30 seconds for a 10-minute video

#### Edge Cases

- No face visible (product demo, screen recording) → fall back to center crop with smooth pan
- Fast camera movement → interpolate tracking, reduce pan speed
- Multiple faces far apart → track primary speaker (detected by diarization), secondary faces cropped
- Face partially occluded → predict position from velocity, recover when visible
- Single static shot → reframe as centered crop, minimal motion

#### Data Flow

```
Video + Face Detection Data
    │
    ▼
Tracking Engine
    ├── Face detection per frame (every 30 frames)
    ├── Interpolate between detected frames
    └── Kalman filter for smooth tracking
    │
    ▼
Keyframe Generation
    ├── Identify critical tracking points
    ├── Generate smooth camera path
    └── Store as reframe metadata (JSON)
    │
    ▼
Preview / Render
    ├── Apply crop with motion
    └── Video filter: crop + pan/zoom
```

#### Performance Targets

| Metric | Target |
|--------|--------|
| Face detection throughput | ≥ 30 fps on RTX 3060 |
| Keyframe generation (10 min video) | < 30 seconds |
| Preview generation (first frame) | < 1 second |
| Reframe metadata file size | < 5 MB per hour of video |

#### Testing Considerations

- Test with talking head videos, product demos, vlogs, interviews, screen recordings
- Test with fast-moving subjects
- Test with occluded faces (sunglasses, masks, hands)
- Test with multiple speakers

---

### F-06: Auto Zoom

#### Overview
Automatically detect emphasis moments and generate cinematic zoom effects. Supports speaker emphasis, emotion emphasis, keyword emphasis, volume spike detection, and manual adjustment.

#### User Stories

| ID | Story |
|----|-------|
| US-F06-001 | As a user, I want the application to automatically zoom in during important moments. |
| US-F06-002 | As a user, I want zoom effects to look smooth and cinematic. |
| US-F06-003 | As a user, I want to manually adjust zoom keyframes. |
| US-F06-004 | As a user, I want to save zoom effect presets. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-ZM-001 | Auto zoom shall detect emphasis moments from audio volume spikes | P0 | §4 |
| PRD-ZM-002 | Auto zoom shall detect emphasis from LLM-identified key phrases | P1 | §4 |
| PRD-ZM-003 | Auto zoom shall detect emphasis from emotional tone analysis | P2 | §4 |
| PRD-ZM-004 | Auto zoom shall apply smooth zoom transitions (ease-in/ease-out, 0.5-1.5s duration) | P0 | §4 |
| PRD-ZM-005 | Auto zoom shall support configurable zoom intensity (1.05x to 2.0x) | P0 | §4 |
| PRD-ZM-006 | User shall be able to add, modify, or delete zoom keyframes | P0 | §4 |
| PRD-ZM-007 | Zoom keyframes shall be editable in the timeline as overlay tracks | P1 | §4 |
| PRD-ZM-008 | Application shall support zoom effect presets (subtle, medium, dramatic) | P2 | §4 |

#### Acceptance Criteria

- AC-ZM-001: Auto zoom identifies ≥ 80% of human-judged emphasis moments
- AC-ZM-002: Zoom transitions appear smooth (no jerky motion) — verified by visual inspection
- AC-ZM-003: Manual keyframe adjustment updates preview within 500ms
- AC-ZM-004: Zoom + reframe work correctly together without conflicting crop regions

#### Edge Cases

- Static content with no emphasis → generate minimal zoom if any
- Zoom target near frame edge → adjust crop to maintain framing
- Very fast emphasis → clamp zoom transition speed
- Combined zoom + reframe → prioritize reframe tracking, apply zoom on top

#### Data Flow

```
Analysis Data (Audio + Transcript + Emotion)
    │
    ▼
Emphasis Detection
    ├── Volume peaks (dB > threshold)
    ├── Keyword emphasis (LLM-identified important phrases)
    └── Emotion transition points
    │
    ▼
Zoom Keyframe Generator
    ├── Place zoom-in at emphasis start
    ├── Place zoom-out 1-2s after
    └── Smooth interpolation between keyframes
    │
    ▼
Timeline Overlay
    └── Zoom keyframes as editable track
```

#### Testing Considerations

- Test with monotone vs. energetic speakers
- Test with music (volume peaks ≠ emphasis)
- Test combined zoom + reframe
- Test rapid emphasis clusters (many keyframes close together)

---

### F-07: Captions

#### Overview
Generate animated captions with word highlighting, multiple styles, karaoke effects, emoji insertion, font library, and subtitle export.

#### User Stories

| ID | Story |
|----|-------|
| US-F07-001 | As a user, I want the application to automatically generate captions with word-level syncing. |
| US-F07-002 | As a user, I want captions to have animated word highlighting (karaoke style). |
| US-F07-003 | As a user, I want to choose from multiple caption styles (fonts, colors, backgrounds). |
| US-F07-004 | As a user, I want to export subtitles in SRT, VTT, and ASS formats. |
| US-F07-005 | As a user, I want emojis to be automatically inserted for emotional emphasis. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-CAP-001 | System shall generate word-level timed captions from transcript data | P0 | §4 |
| PRD-CAP-002 | Captions shall support karaoke-style word highlighting synchronized to audio | P0 | §4 |
| PRD-CAP-003 | System shall include a minimum of 10 caption style presets | P1 | §4 |
| PRD-CAP-004 | Captions shall support custom fonts from the local font library | P1 | §4 |
| PRD-CAP-005 | Captions shall support position (top, bottom, custom), font size, color, background, and outline | P0 | §4 |
| PRD-CAP-006 | System shall support automatic emoji insertion at emotional high points | P2 | §4 |
| PRD-CAP-007 | System shall support multiple caption tracks for multi-language | P1 | §4 |
| PRD-CAP-008 | Captions shall be rendered as an overlay during video export | P0 | §4 |
| PRD-CAP-009 | Caption rendering shall be GPU-accelerated | P1 | §4 |
| PRD-CAP-010 | System shall support caption animation (fade in, slide up, bounce, typewriter) | P1 | §4 |
| PRD-CAP-011 | System shall export SRT, VTT, and ASS subtitle formats | P0 | §4 |

#### Acceptance Criteria

- AC-CAP-001: Caption timing matches audio within ±100ms for ≥ 95% of words
- AC-CAP-002: Karaoke highlighting stays perfectly synchronized during playback
- AC-CAP-003: Style changes apply to rendered export without re-processing
- AC-CAP-004: SRT, VTT, and ASS exports are valid and playable in VLC
- AC-CAP-005: Font rendering respects all typographic properties (size, color, weight, line height)

#### Edge Cases

- Very fast speech → merge into grouped word segments
- Overlapping speech (multiple speakers) → display alternating sides or stacked
- Special characters / non-Latin scripts → render correctly (Unicode support)
- Very long caption lines → wrap at configurable max width
- User edits transcript → captions update automatically

#### UI Requirements

- Caption preview on video
- Caption style panel with live preview
- Font picker with system font scanning
- Keyframe editor for caption animation

#### Testing Considerations

- Test with various languages (CJK, RTL, Latin)
- Test caption sync with edited transcript
- Test all animation styles
- Test exported subtitle files in external players

---

### F-08: Translation

#### Overview
Multi-language translation of transcripts and captions with auto-language detection. Supports subtitle and caption translation.

#### User Stories

| ID | Story |
|----|-------|
| US-F08-001 | As a user, I want to translate my transcript into another language. |
| US-F08-002 | As a user, I want the source language to be auto-detected. |
| US-F08-003 | As a user, I want to create translated caption tracks for multi-language export. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-TRN-001 | System shall auto-detect source language from transcript | P1 | §4 |
| PRD-TRN-002 | System shall support translation of transcript into at least 20 languages | P1 | §4 |
| PRD-TRN-003 | System shall support creation of translated caption tracks | P1 | §4 |
| PRD-TRN-004 | System shall maintain word-level timing alignment in translated captions | P2 | §4 |
| PRD-TRN-005 | Translation shall use the configured LLM/translation provider | P1 | §3.4, §3.6 |
| PRD-TRN-006 | Translation may use a dedicated translation model (NLLB, M2M-100) | P2 | §3.4 |

#### Acceptance Criteria

- AC-TRN-001: Auto-detection correctly identifies language for top-20 languages with ≥ 90% accuracy
- AC-TRN-002: Translation preserves meaning (human evaluation: ≥ 4/5 for key content)
- AC-TRN-003: Translated captions align within 500ms of original timing
- AC-TRN-004: Language switching does not require re-processing the entire pipeline

#### Edge Cases

- Code-switching (mixed languages in one video) → translate each segment by detected language
- Non-translatable content (music, sound effects) → carry over untranslated
- Technical jargon → preserve original term with translated explanation
- Very long transcript → chunk into segments for translation context

#### Dependencies

- LLM plugin or NLLB model
- Language detection library (fastText, lingua)

---

### F-09: AI Voice Processing

#### Overview
Voice enhancement, noise reduction, audio normalization, silence removal, voice cloning, and AI dubbing capabilities.

#### User Stories

| ID | Story |
|----|-------|
| US-F09-001 | As a user, I want to reduce background noise in my audio. |
| US-F09-002 | As a user, I want audio levels to be normalized across my clip. |
| US-F09-003 | As a user, I want long silences to be automatically removed. |
| US-F09-004 | As a user, I want to enhance voice clarity. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-VOICE-001 | System shall provide noise reduction using spectral gating (noisereduce) | P1 | §4 |
| PRD-VOICE-002 | System shall provide audio normalization to configurable LUFS level (default: -14 LUFS) | P0 | §4 |
| PRD-VOICE-003 | System shall remove silences longer than configurable threshold (default: 0.5s) | P1 | §4 |
| PRD-VOICE-004 | System shall provide voice clarity enhancement (EQ-based) | P2 | §4 |
| PRD-VOICE-005 | Voice processing shall be non-destructive — original audio preserved | P0 | §4 |
| PRD-VOICE-006 | Voice cloning shall be supported via Coqui-AI or similar local model | P2 | §4 |
| PRD-VOICE-007 | AI dubbing shall be supported via voice cloning + translated transcript | P2 | §4 |

#### Acceptance Criteria

- AC-VOICE-001: Noise reduction reduces background noise by ≥ 10dB without audible artifacts
- AC-VOICE-002: Normalization adjusts loudness to target LUFS within ±1 LU
- AC-VOICE-003: Silence removal does not cut off any speech
- AC-VOICE-004: Voice processing does not increase processing time by more than 20% of source duration

#### Data Flow

```
Original Audio → Voice Processing Pipeline
    ├── Noise reduction (noisereduce)
    ├── Audio normalization (pyloudnorm)
    ├── Silence removal (pydub silence ops)
    ├── Voice enhancement (EQ)
    └── Output processed audio
```

#### Testing Considerations

- Test with various noise types (fan, traffic, room echo, wind)
- Test with whispered, shouted, and normal speech
- Test voice cloning for intelligibility

---

### F-10: AI Visual Generation

#### Overview
AI-powered visual content generation: thumbnails, B-roll suggestions, stock footage integration, and AI image generation.

#### User Stories

| ID | Story |
|----|-------|
| US-F10-001 | As a user, I want the application to auto-generate a thumbnail for my clip. |
| US-F10-002 | As a user, I want to see multiple thumbnail variants. |
| US-F10-003 | As a user, I want AI-suggested B-roll footage for my video. |
| US-F10-004 | As a user, I want to generate images with AI for visual enhancement. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-VIS-001 | System shall auto-generate a thumbnail from the most visually interesting frame | P1 | §4 |
| PRD-VIS-002 | System shall generate multiple thumbnail variants (3-5) | P1 | §4 |
| PRD-VIS-003 | Thumbnail generation shall score frames by visual interest (composition, faces, text) | P2 | §4 |
| PRD-VIS-004 | System shall suggest B-roll timestamps based on transcript | P2 | §4 |
| PRD-VIS-005 | System shall integrate with local image generation models (Stable Diffusion) | P2 | §4 |
| PRD-VIS-006 | Thumbnails shall be editable — text overlay, filters, crop | P1 | §4 |
| PRD-VIS-007 | Stock footage suggestion shall search local or optional Pexels/Unsplash API | P2 | §4 |

#### Acceptance Criteria

- AC-VIS-001: Generated thumbnail is visually appealing (human eval: ≥ 4/5)
- AC-VIS-002: Thumbnail variants are sufficiently different (different frames, not near-identical)
- AC-VIS-003: B-roll suggestions align with transcript content (relevant to keywords)

#### Edge Cases

- Video has no visually interesting frames → generate from middle segment with text overlay
- Dark video → boost exposure for thumbnail candidate frames
- B-roll suggestion for abstract topics → offer text overlay suggestion instead

---

### F-11: AI Content Generation

#### Overview
AI-powered content creation: titles, descriptions, hashtags, SEO optimization, CTAs, hook improvement, and script summarization.

#### User Stories

| ID | Story |
|----|-------|
| US-F11-001 | As a user, I want the application to generate a title for my clip. |
| US-F11-002 | As a user, I want the application to generate a description with hashtags. |
| US-F11-003 | As a user, I want suggestions for improving my video's hook. |
| US-F11-004 | As a user, I want the video to be summarized into a short script. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-CONT-001 | System shall generate 3-5 title suggestions per clip | P1 | §4 |
| PRD-CONT-002 | System shall generate a description (100-300 characters) | P1 | §4 |
| PRD-CONT-003 | System shall generate 5-15 relevant hashtags | P1 | §4 |
| PRD-CONT-004 | System shall suggest hook improvements by analyzing first 3 seconds | P2 | §4 |
| PRD-CONT-005 | System shall generate CTA suggestions for the end of clips | P2 | §4 |
| PRD-CONT-006 | System shall summarize long-form videos into short scripts | P2 | §4 |
| PRD-CONT-007 | All generated content shall be editable by the user | P0 | §4 |
| PRD-CONT-008 | SEO optimization suggestions for YouTube/TikTok metadata | P2 | §4 |

#### Acceptance Criteria

- AC-CONT-001: Generated titles are descriptive and relevant (human eval: ≥ 4/5)
- AC-CONT-002: Hashtags are at least 70% relevant to video content
- AC-CONT-003: Hook suggestions are actionable (specific timing + content suggestions)

#### Dependencies

- LLM provider plugin

---

### F-12: AI Assistants

#### Overview
Conversational AI assistants for editing help, video analysis Q&A, prompt assistance, content coaching, and SEO coaching.

#### User Stories

| ID | Story |
|----|-------|
| US-F12-001 | As a user, I want to chat with an AI about my video content. |
| US-F12-002 | As a user, I want the AI to help me improve my clip. |
| US-F12-003 | As a user, I want the AI to suggest editing improvements. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-ASST-001 | System shall provide a chat interface for video Q&A | P2 | §4 |
| PRD-ASST-002 | Chat context shall include transcript, scenes, and analysis results | P2 | §4 |
| PRD-ASST-003 | System shall provide an editing assistant that can suggest timeline operations | P2 | §4 |
| PRD-ASST-004 | System shall provide a content coach for improving hooks, titles, and descriptions | P2 | §4 |
| PRD-ASST-005 | System shall provide SEO recommendations for export platforms | P2 | §4 |
| PRD-ASST-006 | Chat interface shall support streaming responses | P2 | §4 |

#### Acceptance Criteria

- AC-ASST-001: Chat responses reference specific timestamps in the video
- AC-ASST-002: Editing suggestions are actionable (e.g., "Trim 0:15-0:18, the speaker pauses")

#### Dependencies

- LLM provider plugin
- WebSocket for streaming

---

### F-13: Export

#### Overview
Export processed clips in multiple formats including video files, subtitle files, project interchange XML, and JSON metadata.

#### User Stories

| ID | Story |
|----|-------|
| US-F13-001 | As a user, I want to export my clip as MP4 with H.264/H.265 encoding. |
| US-F13-002 | As a user, I want to export subtitles separately as SRT or VTT. |
| US-F13-003 | As a user, I want to export project data for other NLEs (Premiere, DaVinci, FCP). |
| US-F13-004 | As a user, I want high-quality export with configurable bitrate. |
| US-F13-005 | As a user, I want GPU-accelerated encoding. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-EXP-001 | System shall export video as MP4 (H.264/H.265) | P0 | §4 |
| PRD-EXP-002 | System shall export video as MOV (ProRes, H.264) | P1 | §4 |
| PRD-EXP-003 | System shall export video as WebM (VP9) | P1 | §4 |
| PRD-EXP-004 | System shall export subtitles as SRT, VTT, ASS | P0 | §4 |
| PRD-EXP-005 | System shall export EDL (Edit Decision List) | P2 | §4 |
| PRD-EXP-006 | System shall export Premiere Pro XML | P2 | §4 |
| PRD-EXP-007 | System shall export DaVinci Resolve XML | P2 | §4 |
| PRD-EXP-008 | System shall export Final Cut Pro XML | P2 | §4 |
| PRD-EXP-009 | System shall export project metadata as JSON | P1 | §4 |
| PRD-EXP-010 | Export shall support configurable resolution, bitrate, and frame rate | P0 | §4 |
| PRD-EXP-011 | Export shall use GPU acceleration when available (NVENC, AMF, VideoToolbox) | P0 | §3.5 |
| PRD-EXP-012 | Export shall support batch export of multiple clips | P1 | §4 |
| PRD-EXP-013 | Export progress shall be reported via WebSocket | P0 | §3.3 |
| PRD-EXP-014 | Export shall support background processing | P0 | §4 |

#### Acceptance Criteria

- AC-EXP-001: 60-second 1080p clip exports in < 30 seconds with NVENC (RTX 3060)
- AC-EXP-002: Exported MP4 plays correctly in VLC, Chrome, and QuickTime
- AC-EXP-003: Exported SRT file is valid per W3C specification
- AC-EXP-004: Export preserves caption styling (ASS format)
- AC-EXP-005: Export at 4K resolution does not crash or OOM

#### Export Quality Presets

| Preset | Video Codec | Bitrate | Audio | Use Case |
|--------|-------------|---------|-------|----------|
| High Quality | H.264 | 50 Mbps | 320k AAC | Archival |
| Standard | H.264 | 20 Mbps | 192k AAC | Social media |
| Web Optimized | H.265 | 10 Mbps | 128k AAC | Web upload |
| Proxy | H.264 | 5 Mbps | 96k AAC | Draft review |

#### Data Flow

```
Timeline + Effects + Captions → Export Controller
    │
    ▼
FFmpeg Command Builder
    ├── Select codec (H.264/H.265/VP9/ProRes)
    ├── Configure bitrate, resolution, frame rate
    ├── Apply filter chain (crop, zoom, captions)
    └── Set GPU encoder (NVENC/AMF/Videotoolbox)
    │
    ▼
Process Management
    ├── Spawn FFmpeg subprocess
    ├── Monitor progress (parse stderr)
    └── Report via WebSocket
    │
    ▼
Export File
    └── Saved to exports directory
```

#### Testing Considerations

- Test all codec options
- Test with GPU acceleration on and off
- Test with very long exports
- Test export cancellation
- Test exported files in external editors

---

### F-14: Batch Processing

#### Overview
Process multiple videos in a queue with background jobs, resume capability, and scheduled processing.

#### User Stories

| ID | Story |
|----|-------|
| US-F14-001 | As a user, I want to add multiple videos to a processing queue. |
| US-F14-002 | As a user, I want to see queue progress for all items. |
| US-F14-003 | As a user, I want to resume processing if the application is restarted. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-BATCH-001 | System shall support adding multiple videos to a processing queue | P1 | §4 |
| PRD-BATCH-002 | System shall process queue items sequentially by default, with optional parallel processing | P1 | §4 |
| PRD-BATCH-003 | System shall persist the queue state to survive application restarts | P1 | §4 |
| PRD-BATCH-004 | System shall report per-item and overall queue progress | P1 | §4 |
| PRD-BATCH-005 | System shall support queue reordering | P2 | §4 |
| PRD-BATCH-006 | System shall support scheduled processing (e.g., process at specific time) | P2 | §4 |
| PRD-BATCH-007 | System shall support per-item configuration (profile, export format, reframe settings) | P1 | §4 |

#### Acceptance Criteria

- AC-BATCH-001: Queue persists across application restart and resumes from last interrupted item
- AC-BATCH-002: 5 items in queue complete in correct order
- AC-BATCH-003: Cancelling an item does not affect other queue items

#### Data Flow

```
User adds to queue → Queue Controller
    │
    ▼
Queue Database (SQLite)
    ├── Job record with status, progress, config
    └── Persisted for crash recovery
    │
    ▼
Worker Pool (Celery / ThreadPool)
    ├── Pick next pending job
    ├── Process with AI pipeline
    └── Update progress → WebSocket
    │
    ▼
Completion → Notification → UI update
```

---

### F-15: Project Management

#### Overview
Create, open, save, auto-save, version history, backup, restore, duplicate, and archive projects.

#### User Stories

| ID | Story |
|----|-------|
| US-F15-001 | As a user, I want to create a new project with a name and storage location. |
| US-F15-002 | As a user, I want to open a recent project from a list. |
| US-F15-003 | As a user, I want my work to be auto-saved every few minutes. |
| US-F15-004 | As a user, I want to see previous versions of my project. |
| US-F15-005 | As a user, I want to backup my project to an archive. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-PM-001 | System shall support creating projects with name, description, and storage path | P0 | §4 |
| PRD-PM-002 | System shall display recent projects with preview thumbnails | P0 | §4 |
| PRD-PM-003 | System shall auto-save project state every 60 seconds (configurable) | P0 | §4 |
| PRD-PM-004 | System shall save project state on every significant editing operation | P0 | §4 |
| PRD-PM-005 | System shall maintain version history (last 10 versions, configurable) | P1 | §4 |
| PRD-PM-006 | System shall support project duplication (copy all assets + metadata) | P1 | §4 |
| PRD-PM-007 | System shall support project archiving (compress to ZIP and move) | P2 | §4 |
| PRD-PM-008 | System shall support project restore from version history | P1 | §4 |
| PRD-PM-009 | System shall restore the last opened project on application start | P1 | §4 |
| PRD-PM-010 | System shall save project metadata to SQLite database | P0 | §3.3 |

#### Acceptance Criteria

- AC-PM-001: Creating a project creates the directory structure and database entry within 1 second
- AC-PM-002: Auto-save triggers within 60 seconds of the last edit
- AC-PM-003: Opening a recent project restores all timeline state, clips, settings, and undo history
- AC-PM-004: Version history captures and restores project state at each save point
- AC-PM-005: Project duplication preserves all media references (no deep copy, use source references)

#### Project Directory Structure

```
~/LocalClip/Projects/{ProjectName}/
├── project.db              # SQLite database (project metadata)
├── config.json             # Project-specific settings
├── sources/                # Original imported videos
│   └── {hash}.{ext}
├── proxies/                # Proxy-encoded videos
│   └── {hash}_720p.mp4
├── exports/                # Rendered output
│   └── {clip_name}.mp4
├── cache/                  # Processing artifacts
│   ├── frames/             # Extracted frames
│   ├── audio/              # Extracted audio
│   └── analysis/           # Pipeline results (JSON)
├── thumbnails/             # Project preview images
└── versions/               # Version history snapshots
    └── v_{timestamp}.json
```

#### Error Handling

- Project file corrupted → attempt recovery from auto-save, then version history, then prompt to create new
- Source video moved/deleted → show "Media offline" indicator, allow relinking
- Disk full during save → warn user, suggest cleanup

---

### F-16: AI Provider Management

#### Overview
Configure and manage AI providers. Support 14+ providers with enable/disable, API keys, model selection, temperature, timeout, retry, and fallback.

#### User Stories

| ID | Story |
|----|-------|
| US-F16-001 | As a user, I want to configure which AI provider is used for each AI task. |
| US-F16-002 | As a user, I want to use local AI models by default without any configuration. |
| US-F16-003 | As a user, I want to connect to OpenAI as an alternative provider. |
| US-F16-004 | As a user, I want providers to fall back if one fails. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-PROV-001 | System shall default to local AI models (Whisper, YOLO, Qwen via llama.cpp) with zero configuration | P0 | §3.4 |
| PRD-PROV-002 | System shall support Ollama as a local AI provider | P1 | §3.4 |
| PRD-PROV-003 | System shall support LM Studio as a local AI provider | P1 | §3.4 |
| PRD-PROV-004 | System shall support OpenAI-compatible API endpoints | P1 | §3.4 |
| PRD-PROV-005 | System shall support OpenAI (GPT-4, Whisper API, etc.) | P1 | §3.4 |
| PRD-PROV-006 | System shall support Anthropic (Claude) | P1 | §3.4 |
| PRD-PROV-007 | System shall support Google Gemini | P1 | §3.4 |
| PRD-PROV-008 | System shall support OpenRouter | P2 | §3.4 |
| PRD-PROV-009 | System shall support Groq | P2 | §3.4 |
| PRD-PROV-010 | System shall support NVIDIA NIM | P2 | §3.4 |
| PRD-PROV-011 | System shall support Together AI | P2 | §3.4 |
| PRD-PROV-012 | System shall support Fireworks AI | P2 | §3.4 |
| PRD-PROV-013 | System shall support DeepInfra | P2 | §3.4 |
| PRD-PROV-014 | System shall support Mistral AI | P2 | §3.4 |
| PRD-PROV-015 | Each provider shall support: enable/disable, API key, base URL, model selection, temperature, max tokens, timeout, retry count | P0 | §3.4 |
| PRD-PROV-016 | Each provider shall support per-AI-task assignment (e.g., use OpenAI for LLM, local for STT) | P1 | §3.6 |
| PRD-PROV-017 | System shall support provider fallback chains (if primary fails, try secondary) | P1 | §3.4 |
| PRD-PROV-018 | System shall allow switching providers without restarting the application | P0 | §3.4 |
| PRD-PROV-019 | API keys shall be stored locally in encrypted configuration | P0 | §3.4, §8 |
| PRD-PROV-020 | API keys shall NEVER be uploaded, synced, or transmitted anywhere | P0 | §3.4 |

#### Acceptance Criteria

- AC-PROV-001: Application works fully offline with local models — no API keys required
- AC-PROV-002: Switching from local LLM to OpenAI takes effect on the next LLM call (no restart needed)
- AC-PROV-003: Provider A fails → automatically uses provider B from fallback chain
- AC-PROV-004: API key field uses password-masked input; key is encrypted at rest
- AC-PROV-005: Each AI task can use a different provider independently

#### Provider Configuration Model

```json
{
  "providers": {
    "openai": {
      "enabled": false,
      "api_key": "enc:AES256:...",
      "base_url": "https://api.openai.com/v1",
      "models": {
        "llm": "gpt-4o",
        "stt": "whisper-1",
        "vision": "gpt-4o"
      },
      "defaults": {
        "temperature": 0.7,
        "max_tokens": 4096,
        "timeout": 60,
        "retry_count": 3
      }
    },
    "ollama": {
      "enabled": true,
      "base_url": "http://localhost:11434",
      "models": {
        "llm": "llama3.2:7b"
      }
    },
    "local": {
      "enabled": true,
      "models": {
        "stt": "whisper-large-v3",
        "vision": "yolov8n-face",
        "embedding": "all-MiniLM-L6-v2"
      }
    }
  },
  "task_routing": {
    "stt": ["local", "openai"],
    "llm": ["local", "ollama", "openai"],
    "vision": ["local"],
    "embedding": ["local"]
  }
}
```

#### Security Requirements

- API keys encrypted at rest using Fernet (symmetric encryption derived from machine ID)
- Never log API keys
- Never include keys in error messages
- Never transmit keys to any external endpoint other than the configured provider

---

### F-17: Plugin System

#### Overview
Extensible plugin architecture allowing third-party AI, export, caption, translation, video effect, and import plugins.

#### User Stories

| ID | Story |
|----|-------|
| US-F17-001 | As a developer, I want to create a plugin that replaces the speech recognition engine. |
| US-F17-002 | As a user, I want to install plugins to extend the application's capabilities. |
| US-F17-003 | As a user, I want plugins to run in a sandboxed environment. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-PLUGIN-001 | Plugin system shall define clear interfaces for each extension point | P0 | §3.6 |
| PRD-PLUGIN-002 | Plugin system shall support STT plugins with standard input/output contract | P0 | §3.6 |
| PRD-PLUGIN-003 | Plugin system shall support LLM plugins | P0 | §3.6 |
| PRD-PLUGIN-004 | Plugin system shall support vision model plugins | P1 | §3.6 |
| PRD-PLUGIN-005 | Plugin system shall support caption engine plugins | P1 | §3.6 |
| PRD-PLUGIN-006 | Plugin system shall support translation plugins | P2 | §3.6 |
| PRD-PLUGIN-007 | Plugin system shall support export format plugins | P1 | §3.6 |
| PRD-PLUGIN-008 | Plugin system shall support video effect plugins | P2 | §3.6 |
| PRD-PLUGIN-009 | Plugin system shall support import source plugins | P2 | §3.6 |
| PRD-PLUGIN-010 | Plugins shall be sandboxed (subprocess or container) for security | P1 | §3.6, §8 |
| PRD-PLUGIN-011 | Plugins shall declare dependencies, version requirements, and permissions in a manifest | P0 | §3.6 |
| PRD-PLUGIN-012 | Plugin manifest shall include: name, version, type, author, description, entry point | P0 | §3.6 |

#### Plugin Interface Contract

```python
# Example: STT Plugin Interface
class STTPlugin(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str, config: dict) -> TranscribeResult:
        """Transcribe audio file and return word-level timestamps."""
        ...

    @abstractmethod
    async def get_models(self) -> list[str]:
        """Return list of available models."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> set[str]:
        """Return set of capabilities (e.g., {'diarization', 'language_detection'})."""
        ...
```

#### Plugin Discovery

- Scan plugin directories on startup
- Load plugin manifests
- Validate dependencies
- Register in plugin registry
- Sandbox execution environment

---

### F-18: Processing Analytics

#### Overview
Analytics for processed videos (not user analytics). Includes clip quality scores, virality prediction, hook analysis, engagement prediction, readability scores, speaking speed, silence ratio, keyword frequency, and emotion timeline.

#### User Stories

| ID | Story |
|----|-------|
| US-F18-001 | As a user, I want to see a quality score breakdown for my clip. |
| US-F18-002 | As a user, I want to see predicted engagement metrics. |
| US-F18-003 | As a user, I want to see speaking speed analysis. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-ANL-001 | System shall display quality score (0-100) with per-dimension breakdown | P0 | §6 |
| PRD-ANL-002 | System shall display virality score with confidence interval | P1 | §4 |
| PRD-ANL-003 | System shall analyze hook strength of first 3 seconds | P1 | §6 |
| PRD-ANL-004 | System shall display engagement prediction (estimated retention curve) | P2 | §4 |
| PRD-ANL-005 | System shall display readability score (Flesch-Kincaid) for transcript | P1 | §4 |
| PRD-ANL-006 | System shall display speaking speed (words per minute) over time | P1 | §4 |
| PRD-ANL-007 | System shall display silence ratio (silence time / total time) | P1 | §4 |
| PRD-ANL-008 | System shall display keyword frequency chart | P2 | §4 |
| PRD-ANL-009 | System shall display emotion timeline (positive/negative/neutral over time) | P2 | §4 |

#### Analytics Display

- Quality score: Circular gauge with breakdown bars
- Engagement prediction: Line chart (time vs. predicted retention)
- Speaking speed: Overlaid on transcript with color coding
- Emotion timeline: Color-coded bar (green=positive, red=negative, gray=neutral)
- Keyword frequency: Word cloud or bar chart

---

### F-19: UI & Workspace

#### Overview
Professional desktop-grade UI with dark/light mode, custom themes, dockable panels, multi-window layout, workspace presets, and keyboard-first workflow.

#### User Stories

| ID | Story |
|----|-------|
| US-F19-001 | As a user, I want a dark mode that looks professional. |
| US-F19-002 | As a user, I want to rearrange panels to my preferred layout. |
| US-F19-003 | As a user, I want to save my workspace layout as a preset. |

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-UI-001 | Application shall default to dark mode | P0 | §7 |
| PRD-UI-002 | Application shall support light mode with warm off-white theme | P0 | §7 |
| PRD-UI-003 | Application shall support custom color themes | P2 | §4 |
| PRD-UI-004 | Application shall support dockable, resizable, collapsible panels | P0 | §4 |
| PRD-UI-005 | Application shall support multi-window layout (pop-out panels) | P2 | §4 |
| PRD-UI-006 | Application shall support workspace presets (save/load panel layout) | P1 | §4 |
| PRD-UI-007 | Application shall support keyboard shortcuts for all major operations | P0 | §4 |
| PRD-UI-008 | Application shall show keyboard shortcut reference (press ?) | P0 | §4 |
| PRD-UI-009 | Application shall open directly into the project browser (no login) | P0 | §3.2 |
| PRD-UI-010 | Timeline panel shall be the primary workspace | P0 | §4 |
| PRD-UI-011 | Application title bar shall show project name | P0 | §4 |

#### Panel Layout (Default)

```
┌─────────────────────────────────────────────────────────┐
│ Title Bar: Project Name | File | Edit | View | Tools    │
├──────────────┬──────────────────────────┬────────────────┤
│ Media Panel  │    PREVIEW / TIMELINE    │ Inspector      │
│ (Sources,    │                          │ (Clip props,   │
│  Clips,      │    ┌────────────────┐    │  Effects,      │
│  Transitions)│    │ Video Preview  │    │  Transforms)   │
│              │    └────────────────┘    │                │
│              │    ┌────────────────┐    ├────────────────┤
│              │    │  Timeline      │    │ Captions Panel │
│              │    │  [tracks with  │    │ (Text, styles, │
│              │    │   waveforms]   │    │  animations)   │
│              │    └────────────────┘    │                │
├──────────────┴──────────────────────────┴────────────────┤
│ Status Bar: Processing queue (3) | GPU: CUDA | Project: v1│
└─────────────────────────────────────────────────────────┘
```

#### Studio Theme (Dark Mode)

| Token | Value |
|-------|-------|
| `--bg-primary` | `#1a1a1a` |
| `--bg-secondary` | `#222222` |
| `--bg-panel` | `#2a2a2a` |
| `--bg-hover` | `#333333` |
| `--border` | `#3a3a3a` |
| `--text-primary` | `#e8e8e8` |
| `--text-secondary` | `#999999` |
| `--accent` | `#c89b5e` (warm gold) |
| `--accent-hover` | `#d4aa6e` |
| `--danger` | `#c45a5a` |
| `--success` | `#5a9e6f` |

#### Studio Theme (Light Mode)

| Token | Value |
|-------|-------|
| `--bg-primary` | `#f5f0eb` |
| `--bg-secondary` | `#ede8e2` |
| `--bg-panel` | `#e5dfd8` |
| `--bg-hover` | `#ddd7cf` |
| `--border` | `#d0c8be` |
| `--text-primary` | `#2c2824` |
| `--text-secondary` | `#7a726a` |
| `--accent` | `#b8894a` |
| `--accent-hover` | `#c99a55` |

---

### F-20: Performance & Acceleration

#### Overview
GPU acceleration, proxy editing, incremental rendering, smart caching, multi-threaded processing.

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-PERF-001 | System shall auto-detect GPU backend on startup (CUDA, MPS, ROCm, CPU) | P0 | §3.5 |
| PRD-PERF-002 | System shall generate proxy videos (720p H.264) on import for smooth timeline playback | P0 | §4 |
| PRD-PERF-003 | System shall use proxy video for timeline editing, source video for export | P0 | §4 |
| PRD-PERF-004 | System shall support incremental rendering — only re-render changed segments | P1 | §4 |
| PRD-PERF-005 | System shall cache analysis results by source video hash | P0 | §4 |
| PRD-PERF-006 | System shall use multi-threaded processing where applicable | P1 | §4 |
| PRD-PERF-007 | System shall limit GPU memory usage to configurable value (default: 80% of available) | P1 | §3.5 |
| PRD-PERF-008 | System shall support CPU-only mode with graceful performance degradation | P0 | §3.5 |
| PRD-PERF-009 | Timeline playback shall target 30fps for proxy video at 720p | P0 | §4 |
| PRD-PERF-010 | System shall warm up AI models on project load (load to GPU memory) | P1 | §4 |

#### Performance Targets

| Operation | Target |
|-----------|--------|
| Timeline playback (proxy) | 30fps smooth |
| Application startup (cold) | < 5 seconds |
| Application startup (warm) | < 2 seconds |
| Project load (1-hour video, analyzed) | < 3 seconds |
| AI model load (Whisper large-v3 to GPU) | < 10 seconds |
| Export throughput (1080p) | > 60fps with NVENC |

---

### F-21: Settings

#### Overview
Comprehensive settings system covering General, Appearance, Storage, GPU, AI Models, AI Providers, API Keys, Export, Keyboard, Cache, and Advanced.

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-SET-001 | Settings shall be organized into categories with clear navigation | P0 | §4 |
| PRD-SET-002 | General settings: language, startup behavior, auto-save interval | P0 | §4 |
| PRD-SET-003 | Appearance settings: theme (dark/light), accent color, panel layout | P0 | §7 |
| PRD-SET-004 | Storage settings: project directory, cache limit, auto-cleanup | P0 | §3.8 |
| PRD-SET-005 | GPU settings: backend selection (auto/CUDA/MPS/ROCm/CPU), memory limit | P0 | §3.5 |
| PRD-SET-006 | AI Models settings: download, update, remove local models | P0 | §3.4 |
| PRD-SET-007 | AI Providers settings: enable/disable, configure all providers | P0 | §3.4 |
| PRD-SET-008 | API Keys settings: encrypted key management per provider | P0 | §3.4 |
| PRD-SET-009 | Export settings: default format, quality preset, output directory | P0 | §4 |
| PRD-SET-010 | Keyboard settings: customizable keyboard shortcuts | P1 | §4 |
| PRD-SET-011 | Cache settings: cache location, size limit, clear cache | P1 | §3.8 |
| PRD-SET-012 | Advanced settings: debug logging, developer mode, plugin directory | P2 | §4 |
| PRD-SET-013 | Settings shall persist to `config.json` in the application directory | P0 | §3.8 |
| PRD-SET-014 | Settings shall take effect without application restart where possible | P0 | §4 |

#### Settings File Location

`~/.localclip/config/settings.json`

---

### F-22: Storage Management

#### Overview
Manage storage across all data categories with automatic cleanup and configurable limits.

#### Functional Requirements

| ID | Requirement | Priority | Vision Trace |
|----|------------|----------|--------------|
| PRD-STOR-001 | Application directory structure shall be created on first launch | P0 | §3.8 |
| PRD-STOR-002 | System shall track storage usage per category | P1 | §3.8 |
| PRD-STOR-003 | System shall support configurable storage limits per category | P1 | §3.8 |
| PRD-STOR-004 | System shall auto-cleanup temp files older than 24 hours | P1 | §3.8 |
| PRD-STOR-005 | System shall auto-cleanup cache files older than 7 days | P1 | §3.8 |
| PRD-STOR-006 | System shall warn when storage exceeds 80% of configurable limit | P1 | §3.8 |
| PRD-STOR-007 | System shall allow selective purge by category | P1 | §3.8 |
| PRD-STOR-008 | System shall display storage dashboard with per-category breakdown | P1 | §3.8 |

#### Application Directory

```
~/.localclip/
├── config/
│   ├── settings.json      # User configuration
│   └── providers.json     # Provider config (encrypted API keys)
├── projects/
│   └── {project_name}/
├── models/
│   ├── whisper/           # WhisperX models
│   ├── yolo/              # YOLO model weights
│   ├── sam/               # SAM model weights
│   ├── llm/               # Local LLM files (GGUF)
│   └── embeddings/        # Embedding model files
├── cache/
│   ├── frames/            # Extracted frames
│   ├── audio/             # Extracted audio chunks
│   └── analysis/          # Cached analysis results
├── logs/
│   ├── app.log            # Application log (rotating)
│   └── pipeline.log       # Pipeline execution log
├── temp/                  # Temporary processing files
└── exports/               # Default export directory
```

---

## 3. Non-Functional Requirements

### NFR-01: Performance

| ID | Requirement | Target | Priority |
|----|-------------|--------|----------|
| NFR-PERF-01 | Cold start time | < 5 seconds | P0 |
| NFR-PERF-02 | Timeline scrub latency | < 100ms | P0 |
| NFR-PERF-03 | Export speed (1080p) | > real-time with GPU | P0 |
| NFR-PERF-04 | Concurrent processing | 2 simultaneous pipelines | P1 |
| NFR-PERF-05 | UI frame rate | 60fps | P0 |

### NFR-02: Reliability

| ID | Requirement | Target | Priority |
|----|-------------|--------|----------|
| NFR-REL-01 | Crash recovery | Auto-save ≤ 60s loss | P0 |
| NFR-REL-02 | Pipeline robustness | Complete ≥ 95% of jobs | P0 |
| NFR-REL-03 | Error reporting | Every error logged with context | P0 |
| NFR-REL-04 | File integrity | SHA-256 verification on import | P1 |

### NFR-03: Security

| ID | Requirement | Target | Priority |
|----|-------------|--------|----------|
| NFR-SEC-01 | API key encryption | AES-256-GCM at rest | P0 |
| NFR-SEC-02 | Path traversal prevention | Validate all file paths | P0 |
| NFR-SEC-03 | Upload validation | FFprobe probe before accept | P0 |
| NFR-SEC-04 | Plugin sandboxing | Subprocess isolation | P1 |

### NFR-04: Privacy

| ID | Requirement | Target | Priority |
|----|-------------|--------|----------|
| NFR-PRIV-01 | Zero telemetry | No data ever leaves the machine | P0 |
| NFR-PRIV-02 | Zero cloud storage | All data stored locally | P0 |
| NFR-PRIV-03 | Zero tracking | No analytics, crash reports, or usage statistics sent externally | P0 |
| NFR-PRIV-04 | API key privacy | Keys used only for user-configured providers | P0 |

### NFR-05: Compatibility

| ID | Requirement | Target | Priority |
|----|-------------|--------|----------|
| NFR-COMP-01 | OS support | Linux, macOS, Windows | P0 |
| NFR-COMP-02 | Browser | Chrome, Firefox, Edge, Safari (latest 2 versions) | P0 |
| NFR-COMP-03 | GPU backends | CUDA 11.8+, MPS (macOS 14+), ROCm 5+ | P0 |
| NFR-COMP-04 | Python | 3.11, 3.12 | P0 |
| NFR-COMP-05 | Node.js | 20 LTS+ | P0 |

---

## 4. Glossary

| Term | Definition |
|------|------------|
| **Proxy** | Lower-resolution copy of source video used for editing performance |
| **STT** | Speech-to-Text — converting audio to text |
| **Diarization** | Identifying who speaks when in audio |
| **Hook** | The engaging opening moment of a clip that captures viewer attention |
| **Virality Score** | Predicted measure of how likely content is to be shared/engaged |
| **Quality Score** | Composite score (0-100) measuring clip quality across multiple dimensions |
| **Smart Reframe** | AI-driven cropping that tracks subjects to maintain framing across aspect ratios |
| **Keyframe** | A point in time defining a property value (position, zoom, opacity) |
| **LLM** | Large Language Model (e.g., Llama, GPT, Claude) |
| **CELERY** | Distributed task queue for background job processing |
| **LUFS** | Loudness Units relative to Full Scale — standard loudness measurement |
| **WER** | Word Error Rate — measure of transcription accuracy |
| **NLE** | Non-Linear Editor — video editing application (Premiere, DaVinci, FCP) |
| **EDL** | Edit Decision List — interchange format for editing timelines |
| **Plugin Sandbox** | Isolated execution environment for third-party plugins |
| **Proxy Editing** | Editing with lower-resolution media for performance |
| **Incremental Render** | Only re-rendering segments that changed since last render |

---

## 5. Traceability Matrix

| Feature Domain | Vision Document Section | PRD Sections |
|----------------|------------------------|--------------|
| Video Import | §4 Feature Scope | F-01 |
| AI Analysis | §4, §5, §6 | F-02 |
| Clip Generation | §4, §6 | F-03 |
| Timeline Editor | §4 | F-04 |
| Smart Reframe | §4, §5 | F-05 |
| Auto Zoom | §4 | F-06 |
| Captions | §4 | F-07 |
| Translation | §4 | F-08 |
| AI Voice | §4 | F-09 |
| AI Visual | §4 | F-10 |
| AI Content | §4 | F-11 |
| AI Assistants | §4 | F-12 |
| Export | §4 | F-13 |
| Batch Processing | §4 | F-14 |
| Project Management | §4 | F-15 |
| AI Provider Mgmt | §3.4 | F-16 |
| Plugin System | §3.6 | F-17 |
| Analytics | §4, §6 | F-18 |
| UI & Workspace | §7 | F-19 |
| Performance | §3.5, §4 | F-20 |
| Settings | §4 | F-21 |
| Storage | §3.8 | F-22 |

---

## 6. Next Steps

**Proceed to Phase 3: Software Requirements Specification (SRS)**

The SRS will translate these product requirements into detailed technical specifications, including:
- Precise API endpoint definitions
- Database schema design
- Service layer interfaces
- Component interaction diagrams
- State machine definitions for each pipeline stage
- Error code catalog
- Detailed test specifications
