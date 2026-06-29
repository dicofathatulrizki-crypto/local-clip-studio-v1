# ADR-016: CQRS for Analysis Read Models

**Status:** 💡 Proposed  
**Date:** 2026-06-29  
**Author:** Principal Software Architect

---

## Context

The AI pipeline produces complex analysis results (transcript, speakers, scenes, topics, keywords, emotions, hooks, chapters) that are read by multiple UI components but updated only by the pipeline. The read and write workloads have different characteristics.

## Decision

Apply CQRS (Command Query Responsibility Segregation) specifically for analysis data. Commands write to the canonical analysis entity. Reads use denormalized projections optimized for specific UI views.

## Read Models

| Read Model | Purpose | Populated By |
|------------|---------|--------------|
| `TranscriptView` | Timeline + transcript panel | Pipeline completion |
| `SceneView` | Scene markers on timeline | Scene detection stage |
| `ClipGalleryView` | Ranked clip cards | Clip generation stage |
| `AnalyticsView` | Quality scores, charts | Scoring stage |

## Rationale

- **Write once, read many** — Analysis written once but read by transcript viewer, timeline, clips, and analytics panels
- **Query optimization** — Each read model is shaped for its UI component; no complex joins
- **Pipeline efficiency** — Pipeline can write results incrementally as stages complete
- **Versioning** — Read models can be versioned independently

## Implementation

```python
# Command side (pipeline writes)
class AnalysisCommandHandler:
    async def handle_transcript_ready(self, event: TranscriptReady) -> None:
        analysis_repo.save_transcript(event.video_id, event.transcript)
        await event_bus.publish(TranscriptViewUpdated(event.video_id))

# Query side (UI reads)
class TranscriptQueryHandler:
    async def get_transcript_view(self, video_id: str) -> TranscriptView:
        return await transcript_view_repo.get(video_id)
```

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Single analysis model | Queries need complex JSON extraction; schema changes affect all readers |
| Event Sourcing | Over-engineered for single-user app; adds replay complexity |
| Full CQRS with separate DBs | Too complex; single SQLite is sufficient with separate cache tables |

## Consequences

- Additional code for maintaining read model projections
- Eventual consistency between command and query (acceptable — pipeline writes then UI refreshes)
- Read model cache invalidation must be explicit
- May be over-engineering if analysis complexity is low (re-evaluate in implementation)

---
