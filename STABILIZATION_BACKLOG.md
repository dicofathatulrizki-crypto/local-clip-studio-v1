# Stabilization Sprint Backlog

> **Generated:** July 3, 2026
> **Source:** PROJECT_FULL_AUDIT_REPORT.md cross-referenced against current codebase
> **Goal:** Resolve every Critical and High item before Phase C begins

---

## Verification Methodology

Every finding from the audit report was tested against the **current codebase** before inclusion. Categories:

- 🔴 **Confirmed Bug** — Reproduced or verified by static analysis; fix required
- ✅ **Already Fixed** — No longer present in current codebase
- 🟡 **Partially Fixed** — Partially addressed or design intent, not full fix
- ⚪ **False Positive** — Not a real issue (design choice, misinterpretation)
- 🔍 **Needs Further Investigation** — Cannot verify without runtime/HW/sandbox

---

## Severity Legend

| Severity | Description |
|----------|-------------|
| **Critical** | Blocks the primary use case or makes the codebase unusable as a whole |
| **High** | Confirmed functional bug, security gap, or test-suite blocker |
| **Medium** | Code quality, debt, or non-blocking correctness issue |
| **Low** | Cosmetic, documentation-only, or future concern |

---

## Phase 1: Critical Bugs

### C1. Video import broken by `await` on synchronous `probe()` (Audit §13.1)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** `import_service.py:275` does `return await self._ffprobe.probe(str(path))` but `FFprobeService.probe()` is synchronous (`def probe`, not `async def`). `await` on a non-coroutine raises `TypeError` unconditionally.
- **Affected files:** `backend/services/import_service.py:275`, `backend/infrastructure/ffmpeg/ffprobe.py:46`
- **Architectural impact:** Primary use case (video import) is non-functional. No workaround.
- **Fix difficulty:** Very Low — remove `await` and/or wrap in `asyncio.to_thread()`
- **Dependencies:** None
- **Tests to run:** `tests/unit/services/test_import_service.py`, `tests/unit/api/test_api_routes.py`

### C2. No CI/CD pipeline (Audit §14.1)
- **Status:** 🔴 Confirmed Bug (process gap, not code)
- **Root cause:** No `.github/workflows/`, no `.pre-commit-config.yaml` — the root cause of most other findings (dead config, broken imports, unfixed lint)
- **Affected files:** Process-wide
- **Architectural impact:** Every change is un-gated; fixes will regress without CI
- **Fix difficulty:** Medium — create GitHub Actions workflow + pre-commit config
- **Dependencies:** C1, H1, H2 (suite must pass before CI is meaningful)

---

## Phase 2: High-Severity Bugs

### H1. Broken test imports abort test suite (Audit §9.1)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** `tests/unit/queue/test_retry.py:10` imports `RetryPolicy`, `RetryState`, `ExponentialBackoff` from `backend.infrastructure.queue.retry`. `RetryPolicy` moved to `models.py`. `RetryState` and `ExponentialBackoff` don't exist anywhere. Same wrong import in `tests/integration/queue/test_queue_integration.py:22`.
- **Affected files:** `tests/unit/queue/test_retry.py:10-12`, `tests/integration/queue/test_queue_integration.py:22`
- **Architectural impact:** `pytest tests/` fails at collection. 0 tests run.
- **Fix difficulty:** Very Low — update imports to `from backend.infrastructure.queue.models import RetryPolicy`; remove references to non-existent classes
- **Dependencies:** None
- **Tests to run:** Full test suite (this fix unblocks it)

### H2. TestDispatcher hangs indefinitely (Audit §9.2)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** `Dispatcher.stop()` in `tests/unit/queue/test_dispatcher.py:test_enqueue_dequeue` does not return. Background asyncio tasks not reliably cancelled/awaited.
- **Affected files:** `backend/infrastructure/queue/dispatcher.py` (stop method), `tests/unit/queue/test_dispatcher.py`
- **Architectural impact:** Queue subsystem shutdown hangs, preventing test suite from completing
- **Fix difficulty:** Medium — add `asyncio.wait_for()` with timeout + fallback cancel in `Dispatcher.stop()`
- **Dependencies:** None (but run after H1 to get clean suite)
- **Tests to run:** `tests/unit/queue/test_dispatcher.py`

### H3. Two SQLAlchemy `Base` classes (Audit §4.1)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** Both `engine.py:24` and `base.py:83` define `class Base(DeclarativeBase)`. 13 of 14 models import from `engine.Base`; Alembic is wired to `base.Base`. `create_all_tables()` uses `engine.Base` and won't create the `settings` table.
- **Affected files:** `backend/infrastructure/database/engine.py:24`, `backend/infrastructure/database/base.py:83`, all 14 model files, `backend/alembic/env.py`
- **Architectural impact:** Alembic autogenerate sees 1/14 tables. Schema migrations are unsafe.
- **Fix difficulty:** Medium — delete one `Base` (keep `base.Base`), update 14 imports + alembic/env.py
- **Dependencies:** None
- **Tests to run:** `tests/unit/database/`, verify no import errors

### H4. `StorageManager` field mismatch (Audit §5.1)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** `StorageLimits.from_settings()` reads `max_project_size_gb`, `max_cache_size_gb`, `max_model_storage_gb` from `settings.storage`, but `StorageSettings` defines `per_project_source_limit`, `global_cache_limit`, `model_storage_limit` (different names, different units).
- **Affected files:** `backend/infrastructure/filesystem/storage_manager.py:65-67`, `backend/config/settings.py`
- **Architectural impact:** `StorageManager` cannot be constructed. 11 test failures in filesystem tests.
- **Fix difficulty:** Low — update `from_settings()` to use the actual field names (with bytes → GB conversion)
- **Dependencies:** None
- **Tests to run:** `tests/unit/test_filesystem.py`

### H5. CORS headers dropped on error responses (Audit §3.3)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** `ErrorHandlingMiddleware` is placed outside `CORSMiddleware` in middleware order. When it constructs a `JSONResponse` for errors, CORS headers are not attached.
- **Affected files:** `backend/api/app.py` (middleware registration order)
- **Architectural impact:** All non-2xx responses are invisible to browser JavaScript across origins. Vite dev server on :5173 cannot read error payloads from API on :8765.
- **Fix difficulty:** Low — reorder middleware so CORSMiddleware is outermost, or attach CORS headers manually
- **Dependencies:** None
- **Tests to run:** `tests/unit/api/test_app_factory.py`

### H6. Unbounded upload memory usage (Audit §13.4/{5.2, 12.4})
- **Status:** 🔴 Confirmed Bug
- **Root cause:** `content = await file.read()` (no size arg) + `dest.write_bytes(content)` in `videos.py:76-77, 103-104`. Entire file buffered in memory. `max_upload_size` never enforced.
- **Affected files:** `backend/api/routes/videos.py:76-77, 103-104`
- **Architectural impact:** OOM risk on large video uploads. Primary import path is unsafe.
- **Fix difficulty:** Low — stream in chunks with `while chunk := await file.read(1024*1024)` and enforce max_upload_size
- **Dependencies:** None
- **Tests to run:** New test or manual verification

### H7. Unsanitized filename in video upload (Audit §12.4)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** `dest = tmp / (file.filename or "video.mp4")` with no sanitization. `pathlib`'s `/` doesn't reject `..` segments.
- **Affected files:** `backend/api/routes/videos.py`
- **Architectural impact:** Path traversal vulnerability (CWE-22) on unauthenticated endpoint
- **Fix difficulty:** Low — use server-generated UUID filename, store original as metadata
- **Dependencies:** H6 (same file/section)
- **Tests to run:** Manual or unit test

### H8. Missing `Awaitable` import in queue files (Audit §2.2)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** `scheduler.py:62,119` and `worker.py:77,101,225,242` use `Awaitable[None]` as type annotation but only import `Callable`. Hidden by `from __future__ import annotations`.
- **Affected files:** `backend/infrastructure/queue/scheduler.py`, `backend/infrastructure/queue/worker.py`
- **Architectural impact:** Fails `typing.get_type_hints()`. Already fails mypy.
- **Fix difficulty:** Very Low — add `from collections.abc import Awaitable` to both files
- **Dependencies:** None
- **Tests to run:** Type check (`mypy backend/`) or import test

### H9. `validate_path()` has zero callers (Audit §12.3/5.3)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** `DirectoryManager.validate_path()` defined but never called anywhere in backend/
- **Affected files:** `backend/infrastructure/filesystem/directory_manager.py:125`
- **Architectural impact:** Path traversal protection is inert. Not wired into any actual code path.
- **Fix difficulty:** Low — wire into video upload path (combined with H7)
- **Dependencies:** H7 (same fix area)
- **Tests to run:** `tests/unit/test_filesystem.py`

### H10. Redundant exception handlers — one is dead code (Audit §3.2)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** Both `ErrorHandlingMiddleware` (middleware.py) and `@app.exception_handler(Exception)` (app.py:181) exist. Middleware intercepts first; app.py handler never fires for route exceptions.
- **Affected files:** `backend/api/app.py:181-189`
- **Architectural impact:** Dead code that misleads future developers
- **Fix difficulty:** Very Low — delete the `@app.exception_handler(Exception)` registration
- **Dependencies:** H5 (CORS fix may change this approach)
- **Tests to run:** `tests/unit/api/test_app_factory.py`

### H11. `is_encrypted()` is non-functional (Audit §12.5)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** `Fernet(value.encode())` in `is_encrypted()` tests if `value` is a valid Fernet **key**, not a valid Fernet **token**. Returns `False` for all real ciphertext.
- **Affected files:** `backend/config/encryption.py:124-130`, `backend/services/provider_service.py:149,426`, `backend/services/settings_service.py:245`
- **Architectural impact:** API keys may be re-encrypted on every save, producing double-encrypted values that fail to decrypt
- **Fix difficulty:** Low — use `try: Fernet(key).decrypt(value.encode())` or store explicit `is_encrypted` flag
- **Dependencies:** None
- **Tests to run:** Encryption unit tests

### H12. Blocking subprocess calls block event loop (Audit §13.2)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** Zero uses of `asyncio.to_thread` or `run_in_executor` in backend/. All FFmpeg/FFprobe calls are blocking `subprocess.run()`.
- **Affected files:** `backend/infrastructure/ffmpeg/ffprobe.py`, `backend/services/import_service.py`, all ffmpeg classes
- **Architectural impact:** Event loop freezes during subprocess calls. No concurrent operations possible.
- **Fix difficulty:** Medium — wrap blocking calls in `asyncio.to_thread()`
- **Dependencies:** C1 (probe fix includes this)
- **Tests to run:** Affected service tests

### H13. Makefile references non-existent `frontend/` directory (Audit §14.2)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** `make dev` and `make install` do `cd frontend && ...` but no `frontend/` directory exists
- **Affected files:** `Makefile`
- **Architectural impact:** Dev onboarding is broken at the first command
- **Fix difficulty:** Low — point to `src/` or create a proper frontend directory
- **Dependencies:** None (structural decision)
- **Tests to run:** Manual

### H14. Path-containment bug in PluginSandbox + unconfigured fail-open (Audit §8.2)
- **Status:** 🔴 Confirmed Bug
- **Root cause:** `PluginSandbox.resolve_path()` uses `str(resolved).startswith(str(allowed_dir))` (bad string match) and returns resolved path with no check when `_allowed_dirs` is empty
- **Affected files:** `backend/infrastructure/plugins/sandbox.py` (resolve_path)
- **Architectural impact:** Sibling directory bypass. Fail-open on unconfigured sandbox.
- **Fix difficulty:** Low — use `Path.is_relative_to()` and raise on empty `_allowed_dirs`
- **Dependencies:** None
- **Tests to run:** `tests/unit/plugins/`

---

## Phase 3: Medium-Severity Items

## Sprint 1 — Completed Issues

### H1. Broken test imports (✅ Fixed)
- **Status:** ✅ Fixed
- **Files changed:**
  - `backend/infrastructure/queue/retry.py` — Added `ExponentialBackoff` and `RetryState` classes; added backward-compat methods to `RetryManager` (`register_job`, `get_state`, `can_retry`, `record_retry`, `get_delay`, `remove_job`, `total_retries`); imported and re-exported `RetryPolicy` from `models`
  - `tests/unit/queue/test_retry.py` — Updated `TestRetryPolicy` assertions to use current API field names (`base_delay_seconds`, `backoff_multiplier`)
  - `tests/integration/queue/test_queue_integration.py` — Changed `RetryPolicy` import from `retry` to `models`
- **Tests executed:** `tests/unit/queue/test_retry.py` — 21/21 passed ✅; `tests/integration/queue/test_queue_integration.py` — collects successfully (9 tests) ✅
- **Regression status:** No regressions. Existing `RetryManager.should_retry()` API preserved. Pre-existing 14 queue failures unchanged (test_priority, test_progress, test_models, test_exceptions — separate issues)

---

## Sprint 2: Remaining Issues

| ID | Finding | Status | Fix |
|----|---------|--------|-----|
| M1 | Unused `start` variables in cuda_provider.py:189, rocm_provider.py:179 (F841) | 🔴 Confirmed | Remove unused variables |
| M2 | Unused imports (44 F401 findings across backend) | 🔴 Confirmed | `ruff check --fix` |
| M3 | Silent `except: pass` (37 bandit B110 findings) | 🔴 Confirmed | Add `logger.warning()` to bare catches |
| M4 | FFmpeg resolved via bare name, bypassing FFmpegLocator (7.3) | 🔴 Confirmed | Wire locator into DI chain |
| M5 | Missing FFmpeg filter-graph argument escaping (7.2) | 🔴 Confirmed | Implement escape helper |
| M6 | Priority queue test failures (9.3, 4 failures) | 🔍 Needs Investigation | Root-cause and fix |
| M7 | Progress tracker test failure (9.3, 1 failure) | 🔍 Needs Investigation | Root-cause and fix |
| M8 | Domain exception test failures (8 failures) | 🔍 Needs Investigation | Root-cause and fix |
| M9 | WebSocketManager God Object (755 lines, 25 methods) | 🟡 Partially Fixed | Decompose in future refactor |
| M10 | D212/D213 ruff config mismatch (2/3 of all findings) | ✅ Easy Fix | Fix pyproject.toml |
| M11 | `pool_size`/`max_overflow` settings not wired to engine (4.3) | 🔴 Confirmed | Wire settings to engine constructor |
| M12 | Debug mode default from .env.example (3.6) | 🟡 Partially Fixed | Add comment in .env.example |
| M13 | Missing CHANGELOG.md/CONTRIBUTING.md | 🟡 Partially Fixed | Out of scope for sprint |

---

## Phase 4: Low/Informational

| ID | Finding | Status |
|----|---------|--------|
| L1 | Two project scaffolds in one repo (1.2) | 🔴 Confirmed (structural, not code fix) |
| L2 | PluginSandbox is not real sandbox (8.1) | 🟡 Design decision; fix before Phase C plugin distribution |
| L3 | No connection retry for SQLite lock (4.5) | 🟡 Future concern |
| L4 | Dependency vulnerability scanning not done (12.8) | 🟡 Operational gap |
| L5 | Docker/Compose doesn't match docs (14.3) | 🟡 Documentation gap |

---

## Execution Plan

Each task is worked one at a time:
1. Fix the issue
2. Verify the fix (compile check / import check)
3. Run affected tests
4. Ensure no architectural regression
5. Update this report with completion status
6. Proceed to next task

After all Critical and High items are resolved or explicitly justified, run the full test suite and produce the Stabilization Completion Report.
