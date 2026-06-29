"""
Application Service Layer for Local Clip Studio.

Services orchestrate business operations by coordinating domain entities
with infrastructure interfaces. Each service has a single responsibility.

Services:
- ProjectService     — CRUD, archive, restore, duplicate, recent projects
- ImportService      — File validation, hash dedup, copy, proxy generation
- PipelineService    — AI pipeline orchestration, stage management, caching
- ExportService      — FFmpeg command construction, GPU encoder selection
- ProviderService    — AI provider config, model discovery, fallback routing
- PluginService      — Plugin CRUD, health checks, enable/disable
- SettingsService    — Read/write config, validation, encryption
- AnalyticsService   — Quality scores, virality metrics, engagement analysis

Rules:
- Services import from domain and infrastructure interfaces only
- Services never import from API layer
- Dependencies are injected via constructor injection
"""
