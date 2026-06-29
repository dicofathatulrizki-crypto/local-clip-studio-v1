# ADR-015: Domain-Driven Design

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal Software Architect

---

## Context

The application has complex domain logic: video processing pipelines, quality scoring algorithms, clip generation heuristics, and state machine management. A well-structured domain model is essential for maintainability and testability.

## Decision

Adopt Domain-Driven Design (DDD) principles with the following tactical patterns:

- **Entities:** Project, VideoMaster, Analysis, ClipCandidate, ExportJob
- **Value Objects:** TimeRange, QualityScore, BoundingBox, TranscriptSegment
- **Aggregates:** ProjectAggregate (root entity that manages videos, clips, timeline)
- **Domain Events:** VideoImported, AnalysisCompleted, ExportCompleted, ClipGenerated
- **Repositories:** Interface defined in domain, implementation in infrastructure

## Domain Layer Rules

1. **No infrastructure imports** — Domain code is pure Python with no framework dependency
2. **No SQLAlchemy** — Domain entities are plain Python dataclasses
3. **No FastAPI** — Domain logic doesn't know about HTTP
4. **No file system** — File paths are strings; domain doesn't touch the file system
5. **Business logic only** — Scoring algorithms, state transitions, validation rules

## Example Domain Entity

```python
@dataclass
class ClipCandidate:
    id: str
    video_id: str
    time_range: TimeRange
    quality_score: QualityScore | None = None
    status: ClipStatus = ClipStatus.CANDIDATE

    def accept(self) -> None:
        if self.status != ClipStatus.CANDIDATE:
            raise InvalidTransitionError(f"Cannot accept clip in status {self.status}")
        self.status = ClipStatus.ACCEPTED

    def recalculate_score(self, scorer: QualityScorer) -> None:
        self.quality_score = scorer.calculate(self)
```

## Rationale

- **Testability** — Domain logic can be unit-tested without databases or HTTP
- **Maintainability** — Business rules are centralized, not scattered across the codebase
- **Ubiquitous language** — Domain terms (Project, Clip, Transcript) used consistently
- **Isolation** — Changes to infrastructure don't affect business logic

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Active Record (models with DB logic) | Tight coupling to database; hard to test |
| Transaction Script (logic in services) | Violates SRP; services become overly complex |
| Anemic Domain Model (DTOs only) | Business logic leaks into services |

## Consequences

- Additional abstraction layer increases initial development time
- Requires strict discipline in team to maintain layering
- Mapping between domain entities and ORM models required (manual mapping)
- Domain events require event bus or message infrastructure

---
