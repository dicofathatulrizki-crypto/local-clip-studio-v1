# ADR-007: Plugin-Based AI Provider Architecture

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal AI Engineer

---

## Context

The application must support multiple AI providers (local models and external APIs) for STT, LLM, vision, captioning, and translation tasks. The system must not be tied to any single provider. Providers must be swappable without code changes.

## Decision

Implement a plugin-based architecture where each AI capability is accessed through a formal Python abstract base class (interface). Concrete implementations are loaded as plugins. A plugin registry manages discovery, loading, and routing.

## Plugin Interface Pattern

```python
class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str, **kwargs) -> TranscriptResult: ...
    @abstractmethod
    async def load(self, model_id: str) -> None: ...
    @abstractmethod
    async def unload(self) -> None: ...
    @abstractmethod
    async def health_check(self) -> dict: ...
```

## Rationale

- **Decoupling** — Pipeline logic does not import any AI library directly
- **Extensibility** — New providers can be added as plugin packages
- **Testability** — Mock plugins for unit testing
- **User choice** — User selects which provider to use for each task
- **Fallback** — Automatic fallback to next provider if primary fails

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Direct import (if/else chains) | Tight coupling; cannot extend without code changes |
| Configuration flags | Same coupling problem; every provider adds conditionals |
| Microservices | Over-engineered for single-user, local-first app |
| Strategy pattern | Better but still requires importing all providers at module level |

## Consequences

- Plugin interface must be stable (breaking changes break all plugins)
- Plugin discovery adds startup time (scan directories, validate manifests)
- Plugin sandboxing adds complexity (subprocess isolation)
- Built-in plugins provide the default/local functionality

---
