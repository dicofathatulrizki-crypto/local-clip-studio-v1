"""
Domain Layer for Local Clip Studio.

Contains pure business logic with zero dependencies on infrastructure.

Sub-modules:
- entities/     — Core domain entities (Project, Video, Clip, Analysis, Transcript)
- value_objects/ — Immutable value objects (TimeRange, QualityScore, BoundingBox)
- aggregates/   — Aggregate roots (ProjectAggregate, PipelineAggregate)
- events/       — Domain events (VideoImported, AnalysisCompleted, ExportCompleted)

Rules:
- Domain must have ZERO imports from infrastructure, API, or services layers
- All entities are implemented as plain Python dataclasses
- All value objects are frozen (immutable)
- Aggregates enforce business invariants
"""
