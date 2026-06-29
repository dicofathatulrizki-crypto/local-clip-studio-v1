# ADR-011: AI Provider Abstraction with Fallback

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal AI Engineer

---

## Context

The application supports multiple AI providers (local models, Ollama, OpenAI, Anthropic, etc.). When a provider fails, the system should automatically fall back to the next available provider without user intervention. Each AI task type (STT, LLM, vision) may use different providers.

## Decision

Implement a task-router pattern with configurable fallback chains per AI task type. Each task type has a prioritized list of providers. If the primary fails, the next provider in the chain is tried automatically.

## Configuration Model

```json
{
  "task_routing": {
    "stt": ["local:whisper-large-v3", "openai:whisper-1"],
    "llm": ["local:qwen2.5:7b", "ollama:llama3.2", "openai:gpt-4o"],
    "vision": ["local:yolov8n-face"],
    "embedding": ["local:all-MiniLM-L6-v2"]
  }
}
```

## Fallback Behavior

1. Primary provider is tried (based on configured order)
2. If primary fails with a retryable error: retry up to 3 times with exponential backoff
3. If primary fails permanently (OOM, invalid API key): move to next provider
4. If all providers fail: return error with message listing which providers were tried and why each failed

## Rationale

- **Resilience** — Single provider failure doesn't block the pipeline
- **Graceful degradation** — Local models may be smaller/faster but less accurate; fallback to better model
- **User control** — User configures their preferred order
- **Transparency** — Error messages include which providers were tried

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Hardcoded primary | No automatic recovery on failure |
| Manual retry button | Requires user intervention; disrupts batch processing |
| Always-all-providers | Wastes API calls and computing resources |
| Round-robin | Unpredictable; may fail more often with weaker providers |

## Consequences

- Fallback chain is persisted in provider configuration
- Some errors are not retryable (invalid API key, unsupported model)
- Pipeline must be designed to handle partial failures (checkpoint progress)
- User is notified of fallback but pipeline continues

---
