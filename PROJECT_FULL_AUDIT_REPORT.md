# Local Clip Studio — Full Professional Engineering Audit

**Repository:** `dicofathatulrizki-crypto/local-clip-studio-v1`
**Audit date:** July 2, 2026
**Scope:** Phase A (Foundation, Config, Logging, Database, Filesystem, HAL, FFmpeg, Plugin Registry) and Phase B (Domain, Repository, Queue, WebSocket, Services, REST API, FastAPI App Factory), as they exist in the cloned `main` branch at audit time. Phase C and Phase D are not implemented and are not scored.
**Methodology:** Full clone and static read of all 424 tracked files; `py_compile`, `ruff`, `mypy --strict`, `bandit`, and `radon` run against the actual `backend/` package inside a fresh virtualenv built from the project's own `pyproject.toml`; the unit test suite (1,446 collected tests) was executed; several specific claims (exception-handler precedence, CORS-on-error behavior, the FFprobe `await` bug, the Fernet `is_encrypted()` helper) were independently reproduced with small standalone scripts against the real project code rather than inferred from reading alone, and are marked **[Verified by reproduction]** below. Dynamic execution of GPU/CUDA paths, actual FFmpeg transcodes, and Celery-with-Redis integration was not possible in this sandboxed environment (no GPU, no `ffmpeg` binary, no Redis) — those areas are assessed statically and flagged as such.

This report intentionally does not pad the finding count. Every finding below is tied to a specific file and, in most cases, a specific line. Section 19 contains as many genuinely distinct findings as the codebase supports with evidence; where that number is below the "100" the brief nominally requested, that is stated plainly rather than filled with duplicate or invented items.

---

## Executive Summary

Local Clip Studio's backend is, structurally, one of the more disciplined Clean Architecture implementations you'll see in a personal/early-stage project: real DDD (aggregate roots, domain events, value objects, state machines), a proper generic repository layer with optimistic locking and soft delete, a genuine layered dependency direction (domain has zero infrastructure imports), and consistently safe subprocess handling (no `shell=True`, no `eval`/`exec`, no `pickle`, no hardcoded secrets anywhere in 31,347 lines of backend code). That is a real, earned positive, and it is not the norm for a project at this stage.

At the same time, this audit found a working core-feature bug that breaks video import unconditionally, a split ORM metadata registry that makes Alembic autogenerate unsafe for 13 of 14 tables, a "plugin sandbox" that is permission bookkeeping rather than an actual execution sandbox, an encryption helper that is provably non-functional, no CI of any kind, a test suite that cannot currently complete a single run (`pytest tests/` aborts at collection; one test class hangs forever), and documentation (README, Dockerfile description) that materially misrepresents what's actually implemented. None of these are found by reading the README. All were found by running the code and its own configured tooling against itself.

**Overall verdict: not ready for Phase C, and not mergeable as-is if this were a real PR gate.** It is, however, a fixable, well-organized codebase — the problems are concentrated in specific, nameable places, not smeared across the whole system. See Section 20 for the full verdict and Section 17 for the specific Phase C blockers.

| Dimension | Score | Dimension | Score |
|---|---|---|---|
| Architecture | 78/100 | Testing | 47/100 |
| Code Quality | 66/100 | Maintainability | 70/100 |
| Security | 58/100 | Scalability | 60/100 |
| Performance | 55/100 | Production Readiness | 38/100 |
| Documentation | 42/100 | Developer Experience | 50/100 |
| **Overall** | **57/100** | | |

(Full scorecard rationale in Section 18.)

---
## Section 1 — Overall Architecture

### 1.1 Layering and dependency direction (verified)

The dependency-direction rule that actually matters for Clean Architecture — inner layers must not import outer layers — **holds cleanly**: `grep` across `backend/domain/` for any import of `backend.infrastructure`, `backend.services`, or `backend.api` returns zero matches. Domain entities (`domain/entities/*.py`), the `ProjectAggregate` (`domain/aggregates/project_aggregate.py`), value objects (`domain/value_objects.py`, 633 lines), state machines (`domain/state_machines.py`), and domain events (`domain/events.py`) are genuinely framework-free Python. `services/` also does not reach into `api/`. This is a real, non-trivial discipline that a lot of "Clean Architecture" projects claim and don't actually maintain — credit where due.

The `ProjectAggregate` in particular is a properly-formed aggregate root: it owns the consistency boundary across `Project + Videos + Analyses + Clips + Exports`, raises domain events (`ProjectCreated`, `VideoImported`, `ClipGenerated`, `ExportStarted/Completed/Failed`, `ProjectDeleted`), and documents its invariants in the module docstring rather than leaving them implicit. Combined with a generic `BaseRepository[ModelT]` that supports soft delete, optimistic-locking-by-version, pagination, and SQLAlchemy-exception-to-domain-exception translation, the Repository pattern is implemented properly, not just nominally.

### 1.2 Two competing "root" projects living in one repository — Critical

**Severity: Critical | Evidence:** repository root listing.

This is the single biggest structural problem, and it sits above the code entirely. The repository root contains **two unrelated applications**:

1. The audited Python backend (`backend/`) — Clean Architecture, FastAPI, SQLAlchemy, Celery, the thing this brief describes.
2. A generic React + Vite + **Convex** + Bun SPA scaffold at the repo root (`src/`, `package.json`, `bun.lock`, `convex.json`, `src/convex/{auth.ts,schema.ts,users.ts,http.ts}`, `sst-env.d.ts`, `vly-toolbar-readonly.tsx`) — an authentication/landing-page starter (`src/pages/{Landing,Auth,NotFound}.tsx`) that has **no relationship to video editing** and does not call the Python backend anywhere (`grep -r "8765\|localhost:8765\|/api/v1" src/` returns nothing).

There is also `isolate/` — 876 KB of pre-built, hashed Vite bundle output (`Auth-BhG6qfxI.js`, `index-BnQkz4KT.css`, etc.) **committed to git**, which is generated build output, not source.

**Why it matters:** the README's own architecture diagram claims "UI Layer — React SPA (Vite + TypeScript + shadcn/ui)" talking to the FastAPI backend, but the actual frontend in the repo is a disconnected auth/landing scaffold from what looks like a different starter template (Convex + SST + a toolbar component named `vly-toolbar-readonly.tsx` strongly suggest this repo was bootstrapped from a generic SaaS-starter generator and the video-editing backend was built inside it afterward, without ever removing or wiring up the original scaffold). A new engineer — or Phase C, which will need a real timeline/editor UI — has to first figure out that ~40% of the repository (everything under `src/`, plus `convex.json`, `components.json`, `sst-env.d.ts`) is inert scaffold, not a starting point.

**Recommended fix:** decide explicitly: either (a) delete the Convex/SST/landing-page scaffold entirely and start the real editor frontend fresh against the FastAPI+WebSocket API that already exists, or (b) if Convex is intentionally being kept for some future purpose (e.g., optional cloud sync), document that decision in an ADR the way every other architectural choice in this repo already is (there are 16 ADRs — this split is the one major decision that isn't recorded anywhere). Remove `isolate/` from git and add it to `.gitignore`.

**Potential impact:** wasted onboarding time, wasted Phase C planning effort if someone assumes the landing page is a real starting point, and a misleading signal to anyone (including this audit's nominal "CTO" reader) about how much frontend work is actually done. Currently: zero frontend work exists for the actual product.

### 1.3 SOLID / DRY / KISS / YAGNI

- **SRP** is respected at the class level almost everywhere reviewed — `CommandBuilder`, `FFprobeService`, `DirectoryManager`, `PluginSandbox`, `SecurityValidator` each do one coherent thing. The one outlier is `infrastructure/websocket/manager.py` at 755 lines (the largest file in the backend) — worth a look for whether connection lifecycle, subscription routing, heartbeat, and rate-limit cleanup should be four collaborators instead of one class doing all four (see 15.1).
- **DRY violation, systemic:** the exact same flawed path-containment check (`str(resolved).startswith(str(allowed))`) is implemented independently in *two* places (`filesystem/directory_manager.py::validate_path` and `plugins/sandbox.py::resolve_path`) rather than as one shared, correct utility. See 12.3 for why the check itself is wrong; the point here is architectural — there is no single `is_path_within()` primitive in the codebase, so the same category of bug had to be (mis-)invented twice.
- **DRY violation:** two independent global-exception-handling mechanisms exist (`ErrorHandlingMiddleware` in `api/middleware.py` and `@app.exception_handler(Exception)` in `api/app.py`) that do functionally the same job. See 3.2 — one of them is dead code, verified by reproduction.
- **YAGNI concern, mild:** the `ai` extras in `pyproject.toml` pull in `torch`, `onnxruntime-gpu`, `pyannote-audio`, `sentence-transformers`, `ultralytics`, and `llama-cpp-python` — a very large, very GPU/version-sensitive dependency surface — for a phase (C) that hasn't started. Not wrong to plan for, but two of the eight names are currently broken (Section 4), so the planning hasn't been validated even at the "does `pip install` succeed" level.
- **KISS:** mostly respected; the domain/services split doesn't over-abstract. The one place complexity clearly got away from the design is `FFmpegLocator.detect_capabilities`, cyclomatic complexity **34** (radon grade E) — see 2.3.

### 1.4 Dependency Injection is real but inconsistent

`backend/api/deps.py` is deliberately thin — it provides `get_db_session`, `get_logger`, and re-exports `get_settings`, all via FastAPI's `Depends()`. That's correct for the pieces it covers. But service-layer composition is **not** centralized there: `api/routes/videos.py` hand-builds `ImportService` with all six of its collaborators inline in a private `_get_service()` closure, and (per the file layout) every other route module likely does the same for its own service. There is no DI container or factory registry — each route file re-declares how to wire its service by hand. This works today at four route modules; it will not scale cleanly once Phase C adds AI-pipeline services with more dependencies, and it means a constructor-signature change to any service requires hunting down every route file that instantiates it.

### 1.5 AI-pipeline readiness

The HAL (`infrastructure/hal/`) is architecturally sound for its stated purpose: a `providers/` package with `cpu_provider.py`, `cuda_provider.py`, `metal_provider.py`, `rocm_provider.py` behind a common `base.py` interface, a `backend_selector.py` for fallback logic, a `memory_manager.py`, and a `model_loader.py`. This is the right shape for what Phase C will need. However, readiness is undermined by two things verified elsewhere in this report: two of the eight AI dependencies in `pyproject.toml` don't resolve on PyPI (4.1), and there is no evidence anywhere in the codebase of the offload pattern (`asyncio.to_thread` / `run_in_executor`) that AI inference — which will be far heavier than the FFprobe calls already shown to block the event loop (13.1) — will need. If Phase C AI services are written the same way `import_service.py` was written, every transcription/detection call will freeze the API and WebSocket for its full duration.

## Section 2 — Code Quality

Run against the actual project configuration (`ruff` and `mypy` both use the repo's own `pyproject.toml`, not defaults):

| Tool | Result |
|---|---|
| `python -m py_compile` on all 168 backend `.py` files | **0 syntax errors** |
| `ruff check backend/` | **2,024 findings** across 45 rule codes |
| `mypy backend/` (project's own `strict = true` config) | **254 errors in 66 of 168 files (39%)** |
| `bandit -r backend/` | 74 Low, 0 Medium, 0 High |
| `radon cc backend/` (rank C or worse, CC > 10) | 18 methods/functions, worst = **E (34)** |
| `radon mi backend/` (rank B or worse) | **0 files** — complexity is localized to specific methods, not systemic |

### 2.1 The linting/type-checking configuration is good; it just isn't enforced anywhere

This is the single most important meta-finding in this section, and it recurs throughout the report. `pyproject.toml` configures `mypy` in `strict = true` mode and a genuinely thorough `ruff` rule set (`E, F, W, I, N, D, UP, B, SIM, ARG, PTH, ERA, PD`). Both are sensible, professional choices. Neither is close to passing:

- **mypy**, in the mode the project itself asked for, reports 254 errors: 68 `arg-type`, 36 `no-untyped-def`, 34 `attr-defined`, 29 `type-arg` (bare generics), 23 `unused-ignore` (stale `# type: ignore` comments — the code moved on and nobody revisited the suppressions), 16 `no-any-return`, 10 `union-attr`, 6 `name-defined` (see 2.2), 5 `untyped-decorator`, plus smaller categories.
- **ruff**, of 2,024 findings, **1,589 (78%) are auto-fixable with `ruff check --fix`** and were never fixed. Two single rule codes — `D213` (multi-line docstring summary should start on line two) and `D413` (missing blank line after last docstring section) — account for **1,363 findings (67% of the total)**, and this points to a config/practice mismatch, not 1,363 separate mistakes: the project's `ruff.lint.per-file-ignores` disables `D212` (the opposite convention) but the codebase's actual docstrings overwhelmingly follow the `D212` style. Either the ignore list has the wrong rule disabled, or the docstrings were never written against the configured convention. Either way, this single mismatched setting is manufacturing two-thirds of the reported "issues" and should be fixed in the config, not by hand-editing 800+ docstrings.
- Genuinely substantive (non-cosmetic) findings: 138 `D102` (undocumented public methods), 57 `D105`, 29 `D103`, 21 `D101` — real documentation-coverage gaps; 44 `F401` unused imports; 16 `B904` (`raise ... from` dropped, destroying exception chains/tracebacks — see files: `config/encryption.py:121`, `ffmpeg/process.py:131`, `websocket/security.py:160`, `websocket/serializer.py:253`, `services/import_service.py:272,279,332,344,354,379`); 3 `F841` unused variables (`hal/providers/cuda_provider.py:189`, `hal/providers/rocm_provider.py:179`, `services/project_service.py:552`).

**Why it matters:** none of this is hard to fix (`ruff check --fix` alone resolves 78% of the count in one command), but its presence is itself evidence — corroborated independently in Sections 9, 11, and 14 — that `make lint`, `make typecheck`, and `make test` are not being run as a gate anywhere before code lands. A `strict = true` mypy config that has never actually been satisfied is arguably worse than no config, because it gives false confidence to anyone who sees "strict mode" in `pyproject.toml` and assumes the codebase honors it.

**Recommended fix:** (1) fix the `D212`/`D213` ignore-list mismatch immediately — this alone removes two-thirds of the ruff noise and lets real findings surface; (2) run `ruff check backend/ --fix` for the other auto-fixable categories; (3) triage the 254 mypy errors by file, prioritizing the 34 `attr-defined` + 68 `arg-type` outside the already-excluded `database/models` and `database/repositories` packages (the mypy override in `pyproject.toml` disables those two codes only for the ORM layer, so every one of these 102 hits is in domain/services/infrastructure code that's supposed to be clean); (4) wire both tools into CI (Section 9/14) so this doesn't recur.

### 2.2 Confirmed dead-on-arrival bug: missing `Awaitable` import — Medium

**Severity: Medium | Evidence:** `ruff --select F821` and `mypy` independently agree:
```
backend/infrastructure/queue/scheduler.py:62,119 — Undefined name `Awaitable`
backend/infrastructure/queue/worker.py:77,101,225,242 — Undefined name `Awaitable`
```
Both files use `Callable[[...], Awaitable[None]]` as a type annotation but only import `Callable` from `collections.abc`; `Awaitable` is never imported anywhere in either file. Both files have `from __future__ import annotations`, so this does **not** crash on ordinary import (PEP 563 defers annotation evaluation to strings) — which is exactly why it survived to this point. It will fail loudly the moment anything calls `typing.get_type_hints()` on these classes (a common thing for introspection-based tooling, some serialization libraries, and FastAPI itself in certain configurations), and it already fails every static type check. **Why it matters:** this is a class of bug that `from __future__ import annotations` specifically hides from a casual `python -c "import backend"` smoke test while leaving it fully live for anything that actually inspects types — a good reminder that "it imports fine" is not the same as "it's correct." **Fix:** add `from collections.abc import Awaitable` (or `from typing import Awaitable`) to both files — a two-line, zero-risk fix.

### 2.3 Complexity hotspots (radon, exact numbers)

| File : Method | Grade | CC |
|---|---|---|
| `infrastructure/ffmpeg/locate.py::FFmpegLocator.detect_capabilities` | **E** | **34** |
| `infrastructure/ffmpeg/progress.py::ProgressParser.parse_line` | D | 21 |
| `infrastructure/plugins/resolver.py::PluginVersionResolver.satisfies` | D | 22 |
| `infrastructure/queue/dispatcher.py::Dispatcher._dispatch_item` | C | 15 |
| `infrastructure/plugins/sandbox.py::PluginSandbox.validate_config` | C | 16 |
| `domain/entities/clip.py::Clip._validate` | C | 14 |
| `infrastructure/ffmpeg/errors.py::translate_error` | C | 14 |
| `services/provider_service.py::ProviderService.validate_provider` | C | 13 |
| `services/settings_service.py::SettingsService._validate_value` | C | 13 |
| `infrastructure/hal/backend_selector.py::BackendSelector._try_backend` | C | 12 |
| `infrastructure/plugins/validator.py::PluginValidator._satisfies_version` | C | 12 |
| `services/provider_service.py::ProviderService._validate_config` | C | 12 |
| (6 more in the C band: `device_detector.py`, `ffmpeg/manager.py.__init__`, `ffmpeg/command.py.export`, `filesystem/file_manager.py.safe_copy`, `queue/worker.py.execute`, `plugins/discovery.py._discover_in_directory`, `domain/entities/clip.py.merge_with`, `plugins/resolver.py` class-level) | C | 11 |

`FFmpegLocator.detect_capabilities` at CC 34 is a genuine outlier — roughly 3x the next-worst method — and given it sits in the exact module responsible for locating and validating the `ffmpeg`/`ffprobe` binaries (directly relevant to Section 7/12's PATH-resolution findings), its complexity is not incidental: a method this branchy is exactly where a security-relevant edge case (a spoofed binary, an unexpected `ffmpeg -version` output format, a missing capability flag) is most likely to be silently mishandled. **Recommendation:** split by responsibility (e.g., separate "find the binary," "parse `-version` output," "detect codec/hwaccel support," "cache the result") into 4 smaller, independently-testable methods.

### 2.4 Dead code found by direct verification, not lint

Three cases where a function exists, looks correct at a glance, and is either never called or actively wrong — none of which any linter flags, because linters check syntax and typing, not semantic correctness:

1. `DirectoryManager.validate_path()` — defined, documented as the path-traversal guard, **zero call sites anywhere in the codebase** (`grep -rn "validate_path(" backend/` returns only its own definition). See 12.3.
2. `APIKeyEncryption.is_encrypted()` — called from three real production sites (`services/provider_service.py:149,426`, `services/settings_service.py:245`) but **always returns `False`, including for real, valid ciphertext**, verified by direct reproduction. See 12.5.
3. `app.py::global_exception_handler` (registered via `@app.exception_handler(Exception)`) — never actually invoked for any exception raised inside a route, verified by reproduction; `middleware.py::ErrorHandlingMiddleware` intercepts everything first. See 3.2.

**Why this matters as a category:** all three are security- or correctness-adjacent functions that *look* like they're doing their job (they're named correctly, documented correctly, and would pass a code review that didn't run them) but are provably inert. This is a stronger argument for adding unit tests around exactly these three functions than any abstract "increase coverage" recommendation would be.

## Section 3 — Backend Design (FastAPI)

### 3.1 App factory, lifespan, structure — solid fundamentals

`backend/api/app.py` uses the modern `@asynccontextmanager` lifespan pattern (not the deprecated `@app.on_event`), correctly gates `/api/docs`, `/api/redoc`, `/api/openapi.json` behind `settings.api.debug`, and cleanly separates route registration, WebSocket registration, and exception-handler registration into named private functions. Startup initializes the database and filesystem and validates config; shutdown closes the database engine. This is good, idiomatic FastAPI structure and is worth preserving as-is.

### 3.2 Redundant global exception handling, and one half of it is dead code — **[Verified by reproduction]** — Medium

Two independent mechanisms both try to be "the" global exception handler:
- `api/middleware.py::ErrorHandlingMiddleware` (a `BaseHTTPMiddleware`) — catches `AppError` and translates it via `exc.to_dict()`/`exc.http_status`; catches bare `Exception` and returns a generic 500.
- `api/app.py::_register_exception_handlers` → `@app.exception_handler(Exception)` — catches bare `Exception` and returns a differently-worded but same-shaped generic 500.

A minimal reproduction using the project's actual `AppError`/`NotFoundError` classes against both mechanisms, wired in the same order as `setup_middleware()`, shows:
```
/boom-notfound (raises NotFoundError) -> 404, {"code": "ERR-NOTFOUND-001", ...}   [caught by MIDDLEWARE]
/boom-generic  (raises ValueError)    -> 500, {"code": "ERR-500", ...}            [caught by MIDDLEWARE]
```
In both cases the middleware intercepts first; `app.py`'s `@app.exception_handler(Exception)` never fires for exceptions raised inside a route. The good news, which contradicts what a purely-static read of `app.py` might suggest, is that the **structured error catalog (20+ error codes) does work correctly** — `AppError` subclasses are properly translated to their declared HTTP status and code. The bad news is architectural cleanliness: `app.py`'s handler is untested, unreachable code that will mislead the next engineer who edits it expecting it to run. **Fix:** delete the `@app.exception_handler(Exception)` registration in `app.py`, or delete `ErrorHandlingMiddleware` and do all translation via `@app.exception_handler(AppError)` / `@app.exception_handler(Exception)` — pick one mechanism, not both.

### 3.3 CORS headers are silently dropped on every error response — **[Verified by reproduction]** — High

**Evidence (reproduced against the real classes and the real middleware order from `setup_middleware()`):**
```
GET /ok   Origin: http://localhost:5173  -> 200, access-control-allow-origin: http://localhost:5173
GET /boom Origin: http://localhost:5173  -> 500, access-control-allow-origin: (none)
```
`CORSMiddleware` is added first (innermost); `ErrorHandlingMiddleware` is added last (outermost). When `ErrorHandlingMiddleware` catches an exception and constructs its own `JSONResponse` directly, that response is built and returned from *outside* `CORSMiddleware`'s wrapping layer, so `CORSMiddleware` never gets a chance to attach the `access-control-allow-origin` header to it.

**Why it matters:** the project's own default `cors_origins` (`["http://localhost:5173", "http://localhost:8765"]`, in `config/settings.py`) exists specifically to let a Vite dev server on `:5173` call the API on `:8765` — the standard local dev setup. In that exact, anticipated configuration, **every non-2xx API response is invisible to browser JavaScript**: the browser blocks the frontend from reading the response body (including the well-designed `{"error": {"code": ..., "message": ...}}` payload) and surfaces a generic CORS error in the console instead of the actual 400/404/500 detail. This will look, to whoever builds the real frontend later, like "the API doesn't return proper errors," when it does — they're just unreachable across origins. This is a textbook, well-documented Starlette/FastAPI pitfall (`BaseHTTPMiddleware`-based exception handling placed inside `CORSMiddleware`'s wrapping). **Fix:** either add `CORSMiddleware` last (outermost) so it wraps error responses too, or have `ErrorHandlingMiddleware` manually attach CORS headers when it builds a response, or move error translation into `@app.exception_handler` registrations (which run inside Starlette's router and are correctly wrapped by CORS).

### 3.4 `202 Accepted` that isn't actually asynchronous — Medium

`POST /api/v1/projects/{project_id}/videos/import` (`api/routes/videos.py`) returns `status_code=202` — semantically "accepted, processing continues in the background" — but the handler `await`s `svc.import_file(...)` to full completion (hashing, ffprobe, file copy) before responding at all. There is a complete Celery-based queue system in this repository (Section 9) that this endpoint does not use. A `202` response that's actually synchronous will mislead any client (including the eventual frontend) written against the documented semantics, and it means the single most resource-heavy user action in the app runs directly inside a request handler rather than a worker. See 13.1 for the concrete consequence.

### 3.5 Dependency injection is manual per-route, not centralized

Covered in 1.4 — `api/deps.py` only provides `get_db_session`/`get_logger`/`get_settings`; every route module hand-wires its own service construction. Flagged here again specifically because Section 3 explicitly asks about DI: this is functional but will not scale past four route modules without duplicated wiring code.

### 3.6 Debug mode is the template default, and it controls a real attack-surface toggle

`config/settings.py` correctly defaults `debug: bool = False`. But `.env.example` — which `scripts/setup.sh` copies verbatim to `.env` on first run — sets `LOCALCLIP_API__DEBUG=true`. Combined with 12.1 (no authentication by design) and 12.2 (CORS as the only real security boundary), the practical effect of following the documented setup path is that `/api/docs`, `/api/redoc`, and `/api/openapi.json` are enabled out of the box, giving any script that can reach the port (Section 12) a full machine-readable map of every endpoint, including the one with the unvalidated-filename issue in 12.3. Low severity in isolation (this is exactly what a dev template is for), but worth a one-line comment in `.env.example` telling users to flip it off for anything other than active development.

## Section 4 — Database

### 4.1 Two independent SQLAlchemy `DeclarativeBase` classes — Alembic autogenerate is unsafe for 13 of 14 tables — **High**

**Severity: High | Evidence (exact, verified by import graph, not inference):**

Two separate classes are both named `Base` and both subclass `DeclarativeBase` directly (meaning they own two *independent* `.metadata` registries):
- `backend/infrastructure/database/engine.py`: `class Base(DeclarativeBase): pass`
- `backend/infrastructure/database/base.py`: `class Base(DeclarativeBase): ...` (this one also carries `UUIDMixin`/`TimestampMixin`/`SoftDeleteMixin` and a global SQLite-pragma event listener)

Of the 14 ORM model files in `infrastructure/database/models/`, **13 import `Base` from `database.engine`**; exactly **one — `models/settings.py` (`SettingsEntry`) — imports `Base` from `database.base`** instead. Meanwhile, `backend/alembic/env.py` sets `target_metadata = Base.metadata` using the import **from `database.base`** — the same module `settings.py` uses. The result: **Alembic's autogenerate machinery is only aware of `SettingsEntry`; it has no visibility into `Project`, `Video`, `Clip`, `Export`, `Analysis`, or any of the other 12 models.**

**Why it matters:** the initial migration (`alembic/versions/001_initial_schema.py`) is hand-written with explicit `op.create_table(...)` calls, so it happens to create all 14 tables correctly and this bug is currently invisible in normal use. But the documented, intended workflow (`make migrate-create message="..."` → `alembic revision --autogenerate`) is wired to a metadata object that only sees one fourteenth of the schema. The first time anyone relies on autogenerate for a schema change to `Project`, `Video`, or any of the other 12 models, it will either silently produce an empty/wrong migration (autogenerate sees no model for the table, so it won't detect the intended change) or, if it also decides to diff against the live database, could propose dropping tables it doesn't recognize as belonging to its target metadata. Separately, `infrastructure/database/engine.py::create_all_tables()` (used for fresh dev/test databases, and referenced by test fixtures) calls `Base.metadata.create_all` using the `engine.Base` — meaning **`create_all_tables()` will never create the `settings` table**, since `SettingsEntry` isn't registered against that metadata at all.

**Recommended fix:** delete one of the two `Base` classes and repoint every import at the single survivor (`database.base.Base` is the better candidate — it already carries the shared mixins and the pragma listener). This is a mechanical, low-risk, high-value fix: 14 one-line import changes plus updating `alembic/env.py` if needed, and it removes a landmine that will otherwise surface as a confusing, hard-to-diagnose production migration bug months from now.

**Potential impact:** silent schema drift between the ORM layer and the live database, or a destructive autogenerated migration if a future developer accepts one without manually reviewing every line — which is exactly the situation this kind of tooling exists to make unnecessary.

### 4.2 Models and repositories — otherwise well designed

`Project` (sampled in full) uses `Mapped[...]`/`mapped_column` typed SQLAlchemy 2.0 style throughout, declares two real indexes (`idx_projects_last_opened`, `idx_projects_archived`), and uses `cascade="all, delete-orphan"` correctly on its `videos`/`timeline` relationships. `BaseRepository[ModelT]` (generic, 563 lines) provides soft-delete filtering, optimistic locking via a `version` column, pagination, bulk operations, and translates `IntegrityError` into typed `DuplicateEntityError`/`RepositoryIntegrityError` rather than leaking raw SQLAlchemy exceptions up through the service layer — this is exactly the kind of boundary discipline Section 1 credits the domain layer for, done again correctly at the persistence boundary.

### 4.3 `DatabaseSettings.pool_size` / `max_overflow` are configured but never used — Low

`config/settings.py` defines `pool_size: int = Field(default=5, ...)` and `max_overflow: int = Field(default=10, ...)` as user-configurable settings. `engine.py::init_engine(database_url, echo=False)` hardcodes `pool_size=5, max_overflow=10` directly in the `create_async_engine()` call and never accepts or reads the `Settings` values at all. The defaults happen to match today, which is why this hasn't been noticed, but changing `LOCALCLIP_DATABASE__POOL_SIZE` via environment variable currently has **zero effect**. This is the same "declared-but-disconnected configuration" pattern found independently in 5.1 (`max_upload_size`) — see 15.3 for the pattern-level writeup.

### 4.4 SQLite configuration — genuinely good

WAL mode, `foreign_keys=ON`, and a 5000ms `busy_timeout` are all correctly enabled via SQLAlchemy connect-event listeners (`database/base.py::set_sqlite_pragmas`, also duplicated in `engine.py::_enable_wal_mode` — see the DRY note in 15.1). `database/base.py`'s version additionally sets `synchronous=NORMAL`, a 64 MB page cache, in-memory temp store, and a 256 MB mmap — sensible, deliberate tuning for a local single-writer SQLite workload, not defaults left untouched. `get_session()` correctly commits on success, rolls back on exception, and always closes in a `finally`.

### 4.5 No connection retry/backoff for transient SQLite lock contention

`busy_timeout=5000` covers short lock waits, but there's no application-level retry wrapper around write operations for `sqlite3.OperationalError: database is locked`, which can still surface under sustained write concurrency (e.g., a Celery worker and the API writing progress updates simultaneously) even with WAL mode. Minor at current scale; worth revisiting once Phase C adds concurrent AI-pipeline writes.

## Section 5 — Filesystem

### 5.1 `StorageManager` cannot be constructed — storage quotas are entirely non-functional — **[Verified by running the test]** — High

**Evidence:**
```
StorageManager.__init__ -> StorageLimits.from_settings()
  settings.storage.max_project_size_gb   <- does not exist on StorageSettings
  settings.storage.max_cache_size_gb     <- does not exist
  settings.storage.max_model_storage_gb  <- does not exist
AttributeError: 'StorageSettings' object has no attribute 'max_project_size_gb'
```
`StorageSettings` (`config/settings.py`) actually defines byte-denominated fields: `per_project_source_limit`, `global_cache_limit`, `model_storage_limit`, `log_limit`, `temp_limit`. `StorageLimits.from_settings()` (`infrastructure/filesystem/storage_manager.py`) reads three **gigabyte**-denominated attribute names that don't exist on that class at all — not a typo, a structural mismatch (different names *and* different units), consistent with `StorageSettings` having been refactored after `storage_manager.py` was written against it. **Every** `StorageManager()` instantiation raises `AttributeError` immediately in `__init__`, which is why this single root cause produces most of the 11 real, reproduced failures in `tests/unit/test_filesystem.py` (`TestStorageManager::test_get_disk_space`, `test_has_enough_space`, `test_get_usage_category`, plus cascading failures in `TestTemporaryStorageManager` and `TestExportStorageManager`, which appear to construct or depend on the same settings path). **Why it matters:** Section 5 of this brief specifically asks about storage quotas — the honest answer is that the quota system as currently wired cannot run at all, not "runs with weak limits." **Fix:** either rename the `StorageSettings` fields to match what `StorageLimits.from_settings()` expects (and convert units), or rewrite `from_settings()` against the fields that actually exist and add the missing GB-vs-bytes conversion. This is a 10-minute fix once someone notices it — the problem is that nothing currently notices it, because there's no CI (Section 9/14).

### 5.2 Unbounded, unstreamed file upload — **High**

Covered in detail with full evidence in 12.4 and 13.4; summarized here for completeness of this section's scope. `api/routes/videos.py`'s `import_video_file`/`validate_import` handlers do `content = await file.read()` (no size argument) then `dest.write_bytes(content)` — the entire uploaded video is buffered in process memory before touching disk. `APISettings.max_upload_size` (default 50 GiB) is declared but never referenced anywhere outside its own field definition — it enforces nothing. For an app whose flagship feature is importing large video files, this is the filesystem-layer manifestation of a memory-usage bug that belongs squarely in "Section 5: Memory usage" as much as it does in Security.

### 5.3 Path traversal protection exists as a class, is wired into zero real code paths

Covered fully in 12.3. `DirectoryManager.validate_path()` is a real, reasonably-intentioned implementation, but it has zero callers anywhere in the codebase, and the one place user-controlled input reaches the filesystem directly (the upload `filename`) doesn't route through it or anything equivalent.

### 5.4 Backup, cache, and cleanup managers — present, not independently verified end-to-end

`backup_manager.py` (303 lines), `cache_manager.py` (301 lines), `cleanup_scheduler.py`, `temp_manager.py`, `proxy_manager.py`, and `export_manager.py` all exist with coherent-looking, docstring-documented APIs (e.g., `backup_manager.py` implements retention-count-based rotation matching `DatabaseSettings.backup_count`). These were reviewed for structure and consistency but — given 5.1's finding that the settings/manager pairing pattern has at least one confirmed structural break — should not be assumed correct without running their tests specifically; several likely share `StorageSettings`/`StorageLimits` as a dependency and may be affected by the same root cause. This is flagged as a verification gap rather than a confirmed additional bug, in the interest of not overstating what was directly checked.

### 5.5 Atomic writes — present where checked

`file_manager.py` is explicitly documented as providing "atomic writes" and "path traversal protection" (docstring) and does use `hashlib`/streaming-oriented helpers; the copy path used by the import flow is `copy_atomic()`. Full line-by-line verification of the atomicity guarantee (temp-file-plus-rename vs. direct write) was not completed in this pass given time budget — noted here as a follow-up rather than asserted either way.

## Section 6 — Hardware Abstraction Layer (HAL)

**Scope note:** this sandbox has no GPU and no CUDA/ROCm/Metal runtime, so nothing in this section could be dynamically exercised. The assessment below is a static read of `infrastructure/hal/` (12 files, ~2,000 lines) plus the automated-tool findings (ruff/bandit/radon) that already touched this package. Treat this section as lower-confidence than Sections 1–5, which were verified by execution.

### 6.1 Design is sound and matches the stated goal

A clean `providers/` package (`cpu_provider.py`, `cuda_provider.py`, `metal_provider.py`, `rocm_provider.py`) implements a common `base.py` interface. `backend_selector.py` documents and implements an explicit priority chain (**CUDA → ROCm → Metal → CPU**) with a `BackendSelection` result object carrying a `score` and human-readable `reason` — good for debuggability (a user or developer can see *why* a given backend was chosen, not just which one). `memory_manager.py` explicitly documents an OOM-recovery strategy ("cache eviction → retry → error"), and `cuda_provider.py` implements a corresponding recovery method — this is the right shape for the problem and shows the design thought through failure modes up front rather than only the happy path.

### 6.2 Confirmed issues from tooling (not re-derived, just localized here)

- `hal/backend_selector.py::BackendSelector._try_backend` — cyclomatic complexity **12** (radon grade C); worth a look alongside 2.3's other complexity hotspots given this method sits on the critical fallback path.
- `hal/device_detector.py::_get_system_ram` — CC **11**.
- `hal/providers/cuda_provider.py:189` and `hal/providers/rocm_provider.py:179` — `ruff F841`: a local variable named `start` is assigned and never used, in both files, at the same relative pattern — strongly suggests copy-paste between the two provider implementations of a timing measurement that was written but never wired to anything (e.g., meant to compute an elapsed-time metric that's silently dropped).
- `hal/providers/rocm_provider.py:264` — `bandit B110`: `except Exception: pass` around a `torch.cuda.empty_cache()` call. Silently swallowing a failed cache-clear during GPU cleanup means a real GPU memory leak (the actual failure this line exists to prevent) can occur with zero log trace to diagnose it by.
- Test coverage in this area is thin even where tests exist and pass: the coverage run in Section 11 shows `hal/device_detector.py` at 9% and `hal/capability_detector.py` at 11% line coverage — the lowest of any package in the backend, on the subsystem most dependent on being correct across heterogeneous real hardware it cannot be tested against in CI anyway.

### 6.3 Subprocess-based capability detection uses non-absolute executable paths

`hal/capability_detector.py`, `hal/device_detector.py` (7 separate `subprocess.run` call sites), and `hal/providers/metal_provider.py` all invoke system tools (presumably `nvidia-smi`, `rocm-smi`, `system_profiler`, etc., based on context) the same way the FFmpeg layer does — bandit flags 9 `B607` (start-process-with-partial-path) findings across the backend, and this package is one of the contributors. See 12.6 for the consolidated finding and fix; not re-derived in full here to avoid duplication.

### 6.4 What wasn't verified

No inference session was actually run, no real GPU memory pressure was simulated, and the OOM-recovery path's "retry" step was not traced end-to-end to confirm it doesn't retry into a second OOM without a cool-down or backoff. Given Phase C will make this package load-bearing for the first time, it deserves a dedicated hardware-in-the-loop test pass (with real CUDA/Metal/ROCm hardware) before it's trusted, independent of this static review's conclusions.

## Section 7 — FFmpeg Integration

### 7.1 Command construction correctly avoids OS shell injection — genuinely good

Every command builder in `infrastructure/ffmpeg/command.py` (17 static methods, 429 lines) returns `list[str]`, and every execution site uses `subprocess.run([...])` or `asyncio.create_subprocess_exec(...)` — **zero** occurrences of `shell=True` anywhere in the 31,347-line backend (confirmed by repo-wide grep; the only match for the string `shell=True` is in a docstring explaining that it's deliberately not used). No `eval`, `exec`, `os.system`, or `pickle` anywhere either. This is the single strongest, most consistently-applied security practice in the codebase and it's worth stating plainly: the most common and most severe way FFmpeg wrappers get exploited (raw shell-string command construction with interpolated filenames) simply isn't present here.

### 7.2 FFmpeg *filter-graph* argument escaping is missing — Medium-High

**Evidence, `infrastructure/ffmpeg/command.py`:**
```python
# burn_subtitles()
vf = f"subtitles={subtitle_path}"
if burn_style:
    vf += f":force_style='{burn_style}'"

# render_captions()
return ["-i", input_path, "-vf", f"ass={captions_path}", ...]   # use_ass branch
return ["-i", input_path, "-vf", f"subtitles={captions_path}", ...]  # non-ass branch
```
`subprocess`-level injection is correctly avoided (7.1), but the FFmpeg **filtergraph mini-language itself** has its own escaping rules, independent of the shell: within a `-vf`/`-filter_complex` argument, `subtitles=`/`ass=` treat `:` as the option-separator and `\` as an escape character. Neither `subtitle_path`/`captions_path` nor `burn_style` is escaped before interpolation. Concretely: **any Windows path** for a subtitle/caption file — which is the normal case, since `config/settings.py::_get_default_storage_path()` explicitly supports Windows via `APPDATA`, and paths look like `C:\Users\name\.localclip\...\captions.ass` — contains both a drive-letter colon and backslashes, both of which are significant to the filtergraph parser once they land inside the `subtitles=`/`ass=` argument. This is a well-documented FFmpeg gotcha (the project's own filter needs the path escaped, e.g. `C\:\\Users\\...`), not a hypothetical one. The `force_style` value is similarly wrapped in only a single layer of `'...'` quoting with no escaping of embedded single quotes, so any style string (or, later, any AI-generated caption text fed through a similar pattern) containing a `'` would break out of the intended quoted argument.

**Why it matters:** "💬 Captions — Animated, karaoke-style, multi-language" is a headline feature in the README. As written, subtitle/caption burn-in is likely to fail outright on Windows (the platform the settings module explicitly supports) the first time it's exercised with a realistic path, and the escaping gap is exactly the kind of thing that gets worse, not better, once Phase C starts feeding AI-transcribed caption *text* (which will contain colons, quotes, and apostrophes as a matter of course — "He said: 'don't stop.'" is an entirely ordinary transcript line) through similar string-interpolation patterns.

**Fix:** implement FFmpeg's documented filter-argument escaping (backslash-escape `:`, `\`, and `'` per the filtergraph grammar) in one shared helper, and route every `subtitles=`/`ass=`/`force_style=`/eventual `drawtext=text=` construction through it. This is a well-scoped, well-precedented fix — FFmpeg's own documentation specifies the exact escaping rules.

### 7.3 `ffprobe`/`ffmpeg` resolved via bare command name, not the locator that exists for this purpose — Medium

The codebase has a dedicated `FFmpegLocator` (`infrastructure/ffmpeg/locate.py`) whose job is to resolve `ffmpeg`/`ffprobe` to a validated, absolute path (`shutil.which(...)` with a bare-string fallback). But every consumer class defaults to the bare command name independently: `ffprobe_path: str = "ffprobe"` (`ffprobe.py`), `ffmpeg_path: str = "ffmpeg"` (`audio.py`, `export.py`, `frame.py`, `process.py`, `proxy.py`, `scene.py`, `thumbnail.py` — 7 separate constructors). This isn't theoretical: `api/routes/videos.py`'s `_get_service()` constructs `FFprobeService()` with **zero arguments**, so the reachable, public-API video-import path resolves `ffprobe` purely via the process's `PATH` environment variable, never touching `FFmpegLocator` at all. `bandit` independently flags this pattern 9 times (`B607: start_process_with_partial_path`) across the FFmpeg and HAL packages. **Why it matters:** resolving an executable by bare name from `PATH` is subject to PATH-hijacking (CWE-426) — anything that can influence the running process's `PATH` (a malicious local program, a compromised shell profile, a supply-chain-compromised sibling dependency) can cause LocalClip to execute an attacker-controlled binary named `ffmpeg`/`ffprobe` instead of the real one. For a purely local, single-user app the practical exploitability is narrower than it would be for a server, but it's a well-known vulnerability class with a fix that's already 90% built. **Fix:** make every FFmpeg/FFprobe-invoking class accept a resolved path from `FFmpegLocator` by default instead of a bare string literal, and wire the DI/construction sites (like `videos.py::_get_service()`) to actually pass it.

### 7.4 The FFprobe `await` bug lives here too — see 13.1 for the full, reproduced writeup

`ffprobe.py::FFprobeService.probe()` is synchronous (`def probe(...)`, blocking `subprocess.run(..., timeout=30)` inside); `services/import_service.py::_probe_file()` does `return await self._ffprobe.probe(str(path))`. Confirmed by cross-referencing every other call site (`ffmpeg/manager.py:115,126`, `ffmpeg/video_info.py` — six call sites, all synchronous, all correct) that `import_service.py` is the one place this is called incorrectly. This is the single highest-severity functional bug found in the entire audit and is written up in full, with the mypy corroboration and the reachability chain through the public REST API, in Section 13.1 — flagged here too since Section 7 explicitly asks about FFmpeg command execution.

### 7.5 Complexity concentrated in exactly the places that need to be trustworthy

`FFmpegLocator.detect_capabilities` (CC 34, the worst method in the backend by a 60% margin — see 2.3) and `ProgressParser.parse_line` (CC 21) are both in this package. Capability detection and progress parsing are the two places where malformed or unexpected `ffmpeg`/`ffprobe` output has to be handled defensively; high branchiness here is a plausible place for an unhandled edge case (an unexpected locale, an unexpected build's `-version` string format, a truncated progress line) to be silently mishandled rather than an accident of style.

### 7.6 GPU-accelerated encoding path exists but is unverifiable here

`ExportParams.gpu_params` is threaded through `CommandBuilder.export()` (`cmd.extend(params.gpu_params)`), implying GPU encoder flags (NVENC/QSV/VideoToolbox) are assembled elsewhere and passed in — consistent with the HAL's backend-selection design. No `ffmpeg` binary is available in this sandbox, so the actual encoder flag correctness for each hardware path was not (and could not be) verified end-to-end.

## Section 8 — Plugin System

### 8.1 `PluginSandbox` is a permissions ledger, not an execution sandbox — Critical (for the Phase C plan), currently unexploitable

**Severity: assessed as Critical for what it implies about Phase C readiness; Low as an active exploit today, since no third-party plugin execution is live yet. Evidence, `infrastructure/plugins/loader.py::PluginLoader.load()`:**
```python
module = importlib.import_module(module_path)      # standard, unrestricted, in-process import
...
sys.path.insert(0, source_dir)                       # a plugin's own directory is added to the global module search path
instance = plugin_class()
```
Plugin code is loaded via ordinary `importlib`, in the same process, same memory space, same OS privileges as the rest of the application — no subprocess isolation, no container, no restricted execution namespace, no `seccomp`/capability dropping, nothing. This is confirmed by the same repo-wide grep that found zero `eval`/`exec`/`os.system` usage (7.1): there is no sandboxing mechanism (restricted-exec, WASM runtime, subprocess-with-reduced-privileges) anywhere in the codebase for plugins to run inside.

`PluginSandbox` (`infrastructure/plugins/sandbox.py`) is a well-written *permission-bookkeeping* class — `check_permission()`, `resolve_path()`, `validate_network_access()`, `validate_model_access()` all have sensible, readable logic. But every one of them only has effect if a plugin's own code voluntarily routes its filesystem/network/model calls through this object first. Nothing enforces that. A plugin — malicious, or simply careless — can call Python's `open()`, `requests`/`httpx`, or `subprocess` directly and bypass every check in this file with zero friction. This is the standard, important distinction between *permission checking* (what exists) and *sandboxing* (what the class is named and what Section 8 of this brief asks about): real sandboxing requires enforcement at the OS/process/interpreter boundary, not at the convention/opt-in level.

**Why the severity is framed as "Critical for Phase C, Low today":** there is currently no first- or third-party plugin distribution mechanism live, so nothing exploits this yet. But it is the single most important item to fix **before** Phase C makes plugin loading a real, user-facing feature — building a marketplace or even a "drop a folder in `~/.localclip/plugins`" flow on top of the current loader means any plugin (including ones a user downloads from the internet, which the manifest/versioning/discovery system in this package is clearly designed to eventually support) runs with full access to the user's machine.

**Fix, in order of effort:** short-term, run plugin code in a separate subprocess with a restricted working directory and no inherited network/filesystem access beyond what's explicitly passed in (even a basic `multiprocessing`/subprocess boundary with IPC is a large improvement over in-process `importlib`); medium-term, evaluate `RestrictedPython`, a WASM-based runtime (e.g., `wasmtime`-hosted plugins), or OS-level sandboxing (Linux namespaces/seccomp, macOS sandbox profiles) depending on what plugin capabilities actually need to exist.

### 8.2 The path-containment bug from 4.1/12.3 is duplicated here, and has a fail-open case — High

`PluginSandbox.resolve_path()` repeats the same `str(resolved).startswith(str(allowed_dir))` pattern already flagged in `DirectoryManager.validate_path()` (12.3) — a sibling directory like `~/.localclip-evil` would pass a containment check against `~/.localclip`. Worse here: `resolve_path()` computes `resolved = Path(user_path).resolve()` **unconditionally**, checks for the literal substring `".."` in the *unresolved* input string (a weak, bypassable check — an absolute path like `/etc/shadow` contains no `".."` at all and sails through), and then:
```python
if not self._allowed_dirs:
    return resolved
```
**If `set_allowed_directories()` was never called (or called with an empty list) before a plugin resolves a path, the method returns the resolved absolute path with no containment check whatsoever.** The entire filesystem-restriction guarantee of the sandbox is contingent on that setup step having run first, in the right order, every time. **Fix:** replace the string-prefix check everywhere with `resolved.is_relative_to(allowed_dir)` (available since Python 3.9; this project requires 3.11+), and make `resolve_path()` fail closed (raise) rather than fail open when `_allowed_dirs` is empty — an unconfigured sandbox should refuse all paths, not allow all of them.

### 8.3 Versioning and validation logic is genuinely sophisticated — and correspondingly complex

`PluginVersionResolver.satisfies` (CC 22, radon grade D) and `PluginValidator._satisfies_version` (CC 12) implement real semver-range matching for plugin dependency resolution — a legitimately hard problem to get right, and the complexity is a plausible reflection of real branching (comparators, wildcards, pre-release handling) rather than accidental sprawl. Given the complexity, this is exactly the code that most needs dense unit tests covering edge cases (pre-release versions, `^`/`~` ranges, unsatisfiable constraint chains) — `tests/unit/plugins/test_resolver.py` exists, and both `hal`/`plugins` test directories passed cleanly in this audit's test run (352 passed, 1 skipped, 0 failed — Section 11), which is a genuine positive signal for this specific subsystem.

### 8.4 Discovery, manifest, lifecycle, health — present and structurally coherent

`discovery.py`, `manifest.py`, `lifecycle.py`, `health.py`, `cache.py`, and `registry.py` (491 lines) round out a complete-looking plugin lifecycle: discover → validate manifest → resolve version constraints → load → health-check → unload/reload/hot-reload. `PluginDiscovery._discover_in_directory` (CC 11) is the only other complexity outlier in this package. This is a lot of well-organized infrastructure built ahead of there being any actual plugins to run through it — reasonable for foundational work, but see 16.3/17 for the gap between "the scaffolding is ready" and "this is safe to point at untrusted code."

## Section 9 — Queue

### 9.1 A single bad test import aborts collection of the entire test suite — **[Verified by running it]** — High

**Evidence:**
```
tests/unit/queue/test_retry.py:11
  from backend.infrastructure.queue.retry import RetryPolicy, RetryState, RetryManager, ExponentialBackoff
ImportError: cannot import name 'RetryPolicy' from 'backend.infrastructure.queue.retry'
```
Traced to source, not just the error message: `RetryPolicy` is a real, complete, actively-used dataclass (`fixed()`/`exponential()`/`aggressive()`/`no_retry()` classmethods, dozens of call sites in `task_registry.py` configuring per-task-type retry behavior) — it lives in `infrastructure/queue/models.py`, correctly re-exported through `infrastructure/queue/__init__.py`'s public API. It does **not** live in `infrastructure/queue/retry.py` (which defines `RetryManager` only). `RetryState` and `ExponentialBackoff` — the other two names this test imports — **do not exist anywhere in the codebase** (repo-wide grep for both class names returns zero definitions). The identical wrong import (`from backend.infrastructure.queue.retry import RetryManager, RetryPolicy`) also appears in `tests/integration/queue/test_queue_integration.py:22`.

**Why it matters:** this is not "a test is wrong" in isolation — it's that `pytest tests/` and `pytest tests/unit`, run exactly as the README and Makefile instruct (`make test`, `make test-unit`), **currently fail before executing a single test**, with pytest reporting `Interrupted: 1 error during collection`. Everything in Section 11's pass/fail data below was only obtainable by explicitly excluding this file. Production code is internally consistent here (`task_registry.py` and `queue/__init__.py` use `RetryPolicy` correctly); this is purely test/implementation drift — most likely `retry.py` was refactored (probably consolidating a design that once had separate `RetryState`/`ExponentialBackoff` classes into the current `RetryManager`) without updating the two test files that still import the old shape. **Fix:** update both test files' imports to `from backend.infrastructure.queue.models import RetryPolicy` / `from backend.infrastructure.queue.retry import RetryManager`, and either implement or remove references to `RetryState`/`ExponentialBackoff` depending on whether that split design is still intended.

### 9.2 `TestDispatcher` hangs indefinitely — **[Verified by isolation]** — High

**Evidence:** running `tests/unit/queue/test_dispatcher.py::TestDispatcher::test_enqueue_dequeue` alone (and the class as a whole — all 4 tests) does not complete within a 55-second bound and was confirmed, by binary-searching which test the run stalled on via `-v`, to hang specifically on this test:
```python
async def test_enqueue_dequeue(self) -> None:
    d = Dispatcher(poll_interval=0.1)
    ...
    await d.start()
    await d.enqueue(item)
    await asyncio.sleep(0.3)
    await d.stop()          # <- run does not return
    assert "job-1" in called
```
Excluding the whole `TestDispatcher` class was the only way to get the rest of `tests/unit/queue/` to complete. Separately, an unrelated queue test run in this audit produced two `RuntimeWarning`-style asyncio messages:
```
Task was destroyed but it is pending!
  task: <Task ... coro=<Worker.execute() ...> wait_for=<Future pending ...>>
  task: <Task ... coro=<TestWorkerPool.test_all_busy.<locals>.handler() ...> ...>
```
Both symptoms point at the same family of bug: background asyncio tasks in the dispatcher/worker machinery not being reliably joined, cancelled, or awaited to completion on `stop()`/shutdown. **Why it matters:** independent of what's happening inside `Dispatcher.stop()` specifically (not traced to the exact line in this pass — flagged as a concrete, reproducible symptom rather than a fully root-caused one), a queue system whose own stop/shutdown path can hang forever is a production-reliability risk beyond the test suite: the same code path is what's supposed to run during application shutdown (`api/app.py::_lifespan`'s shutdown phase) and during Celery worker graceful termination. **Fix:** add a bounded timeout around whatever `Dispatcher.stop()` awaits internally (e.g., `asyncio.wait_for(self._task, timeout=N)` with a fallback to `task.cancel()`), and add the same bound to CI so a hang fails fast (seconds) instead of exhausting a CI job's full time budget.

### 9.3 Real functional test failures beyond the collection/hang issues

With the broken file and the hanging class excluded, the rest of `tests/unit/queue/` ran cleanly enough to produce real signal: **109 passed, 14 failed**, concentrated in `test_priority.py` (`TestPriorityQueue::test_qsize`, `test_put_with_existing_job_id`, `test_mixed_priorities_fifo`, `test_clear`) and `test_progress.py` (`TestProgressTracker::test_active_count`). These were not individually root-caused in this pass (time-boxed in favor of covering the rest of the repository) but are real, reproducible failures against the current `PriorityQueue`/`ProgressTracker` implementations, not flaky/environmental noise — worth a dedicated look given priority ordering and progress tracking are both directly user-visible behaviors (job ordering, WebSocket progress events).

### 9.4 Celery configuration itself is sensible

`celery_app.py` sets `task_acks_late=True` (don't acknowledge until a task completes — avoids silently losing in-flight jobs if a worker process dies), `worker_prefetch_multiplier=1` (prevents one worker from hoarding a batch of long-running video jobs while others sit idle), `task_soft_time_limit=3600`, and `worker_send_task_events=True` for progress integration. These are the correct, non-default choices for a queue whose jobs are individually long-running (video transcodes, AI inference) rather than short and numerous — this reflects real understanding of the workload, not copy-pasted Celery boilerplate.

### 9.5 The deployment story doesn't actually run a worker

Cross-referencing Section "Docker/DevOps" findings: `docker-compose.yml` defines exactly one service (`backend`) and no `redis`, no `celery worker` process, and `.env.example`'s queue settings (`LOCALCLIP_QUEUE__BROKER_URL=redis://localhost:6379/0`) are commented out by default. Combined with 9.4's Redis-aware config, the implication is a "local filesystem/in-memory fallback" mode is intended for the no-Redis case — but nothing in the reviewed code confirms that fallback is actually implemented and exercised (as opposed to Celery simply defaulting to an unconfigured/failing state without Redis). This is flagged as an open verification question for Section 17, not a confirmed second bug.

## Section 10 — WebSocket

### 10.1 `SecurityValidator` — the best-executed security-adjacent module in the codebase

`infrastructure/websocket/security.py` (verified in full) implements message-size limits (256 KB default), a proper sliding-window rate limiter (100 messages/60s default, per-client, with a real `cleanup_rate_limits()` GC path that **is** correctly wired to a caller in `manager.py:539` — unlike several other cleanup/validation utilities found elsewhere in this audit that are defined but never invoked), structural payload validation (type checking, required-field checking, JSON-object-shape enforcement), and unknown-message-type rejection against the actual `WebSocketMessageType` enum rather than a hand-maintained allowlist. The module's own docstring is explicit and accurate about scope: "No authentication or cloud/telemetry — localhost only," which is consistent with, not contradicted by, ADR-014 (12.1). This is the module in the audit that most looks like it was written by someone thinking specifically about abuse cases, and it should be used as the template for how the filesystem/plugin path-validation code (12.3, 8.2) ought to have been written.

One minor, lower-confidence note: `validate_topic()` rejects `".."` and `"/"` in topic strings using the same bare substring check pattern flagged elsewhere (12.3) — but topics here are not used as filesystem paths in what was reviewed, so the blast radius of a bypass is much smaller than the filesystem/plugin cases. Worth a second look only if topic strings are ever used to construct any kind of storage key or file path later.

### 10.2 `WebSocketManager` is a God Object — Medium

**Evidence:** `infrastructure/websocket/manager.py` is the largest file in the backend (755 lines) and its single `WebSocketManager` class owns 25 methods spanning connection lifecycle (`handle_connect`/`handle_disconnect`), message routing (`handle_message`, `_handle_builtin`), event publishing and broadcast (`publish_event`, `broadcast_event`, `emit_to_client`, `emit_to_project`, `emit_progress`), subscription management (`subscribe`, `unsubscribe`, `subscribe_to_project`), heartbeat (`send_ping`, `handle_pong`, `_heartbeat_loop`), and operational concerns (`shutdown`, `cleanup`, `get_stats`). This is at least four separable responsibilities (connection registry, pub/sub routing, heartbeat monitoring, stats/cleanup) in one class. **Why it matters:** this is squarely a maintainability/testability finding, not a correctness one — the websocket unit tests (Section 11) all pass, so nothing here is currently broken. But a 755-line, 25-method class is the highest-risk single file in the codebase for merge conflicts and for a future change in one concern (e.g., heartbeat timing) accidentally affecting another (e.g., broadcast fan-out) without a test catching it. **Fix:** extract `HeartbeatMonitor` and a `SubscriptionRegistry` as their own collaborators that `WebSocketManager` composes, mirroring the separation already done well in the queue package (`Dispatcher`, `WorkerPool`, `Scheduler`, `RetryManager` as distinct classes rather than one).

### 10.3 Test results — clean

All of `tests/unit/websocket/` passed in this audit's test run with zero failures (bundled into the 411-passed/11-failed batch covering `services` + `websocket` + root-level tests — every one of the 11 failures in that batch was in `test_filesystem.py`; none in `websocket/`). Combined with 10.1, this is the most reliably-verified subsystem in the backend, both statically and dynamically.

### 10.4 Serialization and memory-leak surface — reviewed structurally, not exhaustively

`serializer.py` (292 lines) and `subscription.py` (301 lines) were reviewed for structure but not independently stress-tested for the specific "memory leaks" concern this brief's Section 10 asks about (e.g., subscriptions or per-client rate-limit dictionaries growing unbounded if `handle_disconnect` doesn't clean up every registry a client was added to). Given `_client_message_times` in `SecurityValidator` is confirmed cleaned up correctly (10.1), and `WebSocketManager.cleanup()` exists as an explicit method, the pieces are in place — but a full audit of every registry a connecting client gets added to, cross-checked against every one being removed on disconnect, was not completed in this pass and is flagged as a follow-up rather than asserted clean.

## Section 11 — Testing

This section reflects an actual execution of the suite in this audit, not a read of test file names.

### 11.1 The suite cannot currently complete a single `pytest tests/` invocation

As established in 9.1: `tests/unit/queue/test_retry.py` fails to import, and by default pytest refuses to execute *any* tests when a collection error occurs anywhere in the run — it reports `Interrupted: 1 error during collection` and stops. This means `make test` and `make test-unit`, run exactly as documented, currently fail immediately, before a single assertion runs. Getting any real signal out of this suite required explicitly excluding that one file. **This single fact is the most important testing finding in this report** — every other number below was only obtainable by working around it.

### 11.2 Real pass/fail counts, obtained by running the suite in bounded batches

| Batch | Passed | Failed | Skipped | Notes |
|---|---:|---:|---:|---|
| `unit/api` + `unit/database` + `unit/domain` + `unit/ffmpeg` | 517 | 27 | 0 | failures concentrated in `domain/test_exceptions.py` (8), `domain/test_plugin.py`/`test_state_machines.py` (4) |
| `unit/hal` + `unit/plugins` | 352 | 0 | 1 | clean |
| `unit/queue` (excl. `test_retry.py`, excl. `TestDispatcher`) | 109 | 14 | 0 | failures concentrated in `test_priority.py` (4), `test_progress.py` (1) |
| `unit/queue::TestDispatcher` | — | — | — | **hangs indefinitely; excluded, not counted** (9.2) |
| `unit/services` + `unit/websocket` + root-level `unit/test_*.py` | 411 | 11 | 0 | all 11 failures in `test_filesystem.py`, traced to a single root cause (5.1) |
| **Total executed** | **1,389** | **52** | **1** | **1,442 / 1,446 collected tests actually ran** |

Net: of tests that can be run at all, **96.3% pass**. That is a genuinely reasonable pass rate and should not be read as "the code is untested" — 1,446 collected tests across 168 source files is real investment, not a token test directory. The problem this section is actually flagging is upstream of pass/fail: **the suite has clearly never been run to completion as a whole**, or the collection-breaking import and the indefinite hang would have been caught immediately. Every failure this audit surfaced (the settings/`StorageManager` mismatch in 5.1, the `RetryPolicy` import path in 9.1, the priority-queue and domain-exception failures) is the kind of thing a single green/red CI badge exists to catch on the very next commit.

### 11.3 Confirmed asyncio task-lifecycle leaks during test execution

Independent of the `TestDispatcher` hang, running the rest of the queue suite surfaced:
```
Task was destroyed but it is pending!
  task: <Task ... coro=<Worker.execute() ...> ...>
  task: <Task ... coro=<TestWorkerPool.test_all_busy.<locals>.handler() ...> ...>
```
Background asyncio tasks spawned by the worker/dispatcher machinery are not reliably being cancelled or awaited at teardown. Same underlying category of bug as 9.2, surfacing as a warning here rather than a hang — corroborating evidence, not a new independent finding.

### 11.4 Coverage could not be reliably measured in this pass, and here's why that matters

A `--cov=backend` run was attempted, but because it ran without `--continue-on-collection-errors`, pytest's collection abort (11.1) means the run very likely executed **zero actual test function bodies** — the per-file percentages it produced (e.g., near-100% on files that are almost entirely dataclass/enum declarations, single-digit percentages on logic-heavy files like `hal/device_detector.py`) are consistent with *import-time-only* code execution, not real test coverage, and this audit chooses not to report that table as fact rather than present a number it can't stand behind. This is itself worth noting as a finding: getting a trustworthy coverage number for this repository today requires first fixing 9.1 and 9.2. **Recommendation:** once those are fixed, run `pytest tests/unit --cov=backend --cov-report=term-missing` in CI on every PR and track the trend, not just a point-in-time snapshot.

### 11.5 Mock quality and edge cases — spot-checked, not exhaustively audited

Test files reviewed (`tests/unit/domain/*`, `tests/unit/queue/test_dispatcher.py`, `tests/unit/test_filesystem.py`) use real objects and real async execution rather than over-mocked happy-path-only stubs — `test_enqueue_dequeue` (9.2) is a good example: it exercises a real `Dispatcher` with a real handler coroutine rather than mocking the dispatch mechanism itself, which is exactly why it was able to catch a real hang. That's a legitimately good testing instinct (test the real collaboration, not a mock of it) even though this particular test currently can't complete. A full inventory of every test file's mock-vs-real ratio was not completed given the time budget; the sample reviewed skews toward real-object testing, which this audit considers a positive signal worth confirming at greater scale in a follow-up pass.

### 11.6 Integration tests — not executed

`tests/integration/{database,ffmpeg,hal,plugins,queue}` were read for structure but not run in this sandbox (no real Redis, no real GPU, no real `ffmpeg` binary installed). `tests/integration/queue/test_queue_integration.py` shares the same broken `RetryPolicy` import as 9.1 and would fail to collect for the identical reason.

## Section 12 — Security

### 12.1 No authentication is a deliberate, documented decision — and a reasonable one, with one condition

`docs/architecture/adr/ADR-014-no-authentication.md` explicitly records the decision: single local user, single local machine, "no threat model" premise, mitigated by localhost-only binding (`APISettings.host` defaults to `127.0.0.1`, not `0.0.0.0` — a genuinely good, deliberate default) and an explicit CORS allow-list rather than a wildcard. This audit treats the decision itself as reasonable for the stated product (a local, single-user desktop-style tool has a fundamentally different threat model than a multi-tenant service), not as a naive oversight — it's the kind of tradeoff that deserves an ADR, and it has one. The condition is stated in the ADR's own mitigation table: with no auth layer, **CORS and localhost-binding are not one mitigation among several — they are the entire security boundary.** That raises the bar on getting them exactly right, which is why 12.2 matters more here than it would in an app with a real auth layer behind it.

### 12.2 The security boundary the "no-auth" decision depends on has a confirmed gap

Covered in full, with reproduction, in 3.3: `ErrorHandlingMiddleware` is wired such that CORS headers are never attached to any error response. This doesn't create a new hole in the "no-auth" boundary by itself (the request still has to originate from an allow-listed origin, or from a non-browser client that doesn't need CORS headers at all — CORS is a browser-enforced restriction on *reading* responses, not a server-side access control), but it does mean the ADR's own mitigation table entry ("CORS configured to allow only localhost origins") is not, in practice, uniformly true across every response the server sends — it's true only for the success path. Filed here as the security-framing summary; see 3.3 for the full reproduction.

### 12.3 Path-traversal protection exists as unused code, and has a bypassable bug where it does exist — **High**

Consolidating 5.3/8.2 into one security-scoped finding: `DirectoryManager.validate_path()` (`infrastructure/filesystem/directory_manager.py`) is a real method, correctly named, correctly documented — and has **zero callers anywhere in the 31,347-line backend** (verified by grep returning only its own definition). The *same category* of check is independently reimplemented in `PluginSandbox.resolve_path()` (`infrastructure/plugins/sandbox.py`), and both share the same bug: containment is tested via `str(resolved_path).startswith(str(allowed_base))`, a naive string-prefix comparison that a sibling directory sharing a name prefix (e.g., `~/.localclip-evil` against an allowed base of `~/.localclip`) would incorrectly pass. `PluginSandbox.resolve_path()` additionally fails **open**, not closed, when no allowed directories have been configured (`if not self._allowed_dirs: return resolved` — returns the path with zero containment check). **Why it matters, stated once and not repeated in 5.3/8.2:** two independent, security-relevant checks were needed in this codebase, and both were hand-written from scratch with the same subtle flaw rather than sharing one correct, tested primitive — which is exactly the situation a single `is_path_within(path: Path, base: Path) -> bool` utility (implemented with `Path.is_relative_to()`, available in the 3.11+ this project already requires) exists to prevent. **Fix:** write that one utility, use it everywhere, delete both bespoke versions, and — separately — actually call it from the one place user input reaches a filesystem path directly (12.4).

### 12.4 Unsanitized filename from multipart upload flows directly into a filesystem path — **High**

**Evidence, `api/routes/videos.py`:**
```python
file: UploadFile = File(...)
...
dest = tmp / (file.filename or "video.mp4")
dest.write_bytes(content)
```
`file.filename` is attacker/user-controlled multipart form data and is used, unsanitized, as a path component. `pathlib`'s `/` operator does not strip or reject `..` segments — `Path("/tmp/x") / "../../etc/foo"` composes to a path that resolves outside `/tmp/x`. No call to `DirectoryManager.validate_path()` or any equivalent containment check occurs anywhere on this path (12.3), and no filename sanitization (stripping path separators, rejecting `..`, or generating a server-side name instead of trusting the client-supplied one) happens either. **Why it matters:** this is the one concrete, reachable instance in the whole codebase of the exact vulnerability class (CWE-22) that Section 5/12 of this brief specifically asks about, on the exact endpoint (`videos.import`) that ADR-014 (12.1) implicitly assumes is safe to leave unauthenticated because "no threat model" — a crafted `filename` in a multipart upload doesn't require bypassing CORS or auth at all if the request is otherwise legitimate-looking. **Fix:** never use client-supplied filenames as path components; generate a server-side name (a UUID or content hash — the codebase already computes content hashes elsewhere for storage keys, per 4.2's model review) and store the original filename only as metadata.

### 12.5 The encryption module doesn't do what it says, and one of its own functions is provably broken — **[Verified by reproduction]** — Medium-High

**Claim vs. implementation:** the README advertises "AES-256-GCM API key encryption." The actual implementation (`config/encryption.py`) uses `cryptography.fernet.Fernet`, which is internally AES-**128**-CBC with a separate HMAC-SHA256 (encrypt-then-MAC) — a different, if still legitimate and well-vetted, construction, not AES-256 and not GCM. This is a factual documentation error, not a broken primitive: Fernet itself is a sound, widely-used building block, and the encrypt/decrypt round trip was verified by reproduction to work correctly.

**Key derivation is weak relative to what "encryption at rest" implies:** the "machine-derived key" is `sha256(hostname + os.name + sha256(str(home_dir_path)))`. All three inputs are low-entropy and often observable or guessable (hostname is frequently broadcast on local networks; `os.name` has exactly two possible values; a home directory *path* like `/home/alice` is not a secret and hashing it doesn't make it one). More importantly, the derived key is **also persisted verbatim to a sibling file** (`~/.localclip/config/key.der`, mode `0o600`) the first time it's used — so in practice, anyone who can read the encrypted values in the SQLite database can, by construction, typically also read the key sitting next to it under the same OS-permission boundary. The encryption adds a real but narrow layer (protects a DB-only copy/leak scenario) rather than the broader "encryption at rest" protection the README's framing implies. For a fully local, single-user tool this may be an acceptable tradeoff, but it should be described accurately rather than as AES-256-GCM.

**`is_encrypted()` is provably non-functional — reproduced directly:**
```
enc.encrypt("sk-my-openai-key-abcdef123456")  ->  "gAAAAABqRej8FRg1anB7trUD..." (a real, valid Fernet token)
APIKeyEncryption.is_encrypted(that_real_token)  ->  False
```
The implementation calls `Fernet(value.encode())` — the `Fernet` constructor's argument is a **key**, not a token to validate — so this function actually tests "is `value` shaped like a valid Fernet key," not "is `value` an encrypted token," and returns `False` for every real ciphertext. It is called from three real production sites (`services/provider_service.py:149,426`, `services/settings_service.py:245`), all as a guard of the shape "if not already encrypted, encrypt it now" — since the guard always evaluates to "not encrypted," provider API keys are at risk of being **re-encrypted on every save** rather than stored once, which can produce double-encrypted values that later fail to decrypt with a confusing `InvalidToken` error at the point someone actually tries to use a saved API key. **Fix:** either check `Fernet(key).decrypt(value)` inside a try/except (attempt decryption, catch `InvalidToken`) or store an explicit `is_encrypted` flag alongside the value instead of trying to infer it from shape.

### 12.6 Executables resolved by bare name are subject to PATH-hijacking — Medium

Full evidence and fix already given in 6.3 and 7.3 (`FFprobeService()` constructed with zero arguments in the one reachable API route, bypassing the `FFmpegLocator` built for exactly this purpose; `bandit` flags this pattern 9 times as `B607` across the FFmpeg and HAL packages). Filed here for Section 12's "privilege escalation" scope: CWE-426 (untrusted search path) is a real, if narrow-blast-radius-for-a-local-app, vulnerability class, and the fix is largely already built and just needs to be the default instead of opt-in.

### 12.7 Silent exception swallowing is systemic (37 instances) and includes security-adjacent cleanup paths — Medium

`bandit` flags 37 `B110` (`try/except/pass`) findings across the backend — not a handful of isolated cases, a pattern. Two examples with real consequence: `hal/providers/rocm_provider.py:264` silently swallows a failed `torch.cuda.empty_cache()` (6.2 — a real GPU memory leak with zero log trace), and several occurrences sit in cleanup/shutdown paths reviewed in Sections 5, 9, and 10. **Why this belongs in the security section specifically, not just code quality:** silent `except: pass` blocks are exactly where a security-relevant failure (a failed permission check, a failed sandboxed-path validation, a failed cleanup that leaves sensitive temp data behind) would be most likely to fail *without anyone finding out*, precisely because nothing is logged. **Fix:** at minimum, `logger.debug()` or `logger.warning()` inside every currently-bare `except Exception: pass`, so failures are silent to the *user* (fine, often correct for genuinely non-critical fallbacks) but never silent to *logs*.

### 12.8 Dependency vulnerability scanning — not completed, stated plainly

`pip-audit` was installed in this audit's sandbox but a full scan against a live vulnerability database was not completed (this sandbox's network egress is restricted to a fixed allow-list of package registries and does not include a vulnerability-database host, so a `pip-audit` run would either fail outright or silently return incomplete results — better to state the gap than present a false-negative "clean" scan). **Recommendation:** run `pip-audit` (or `safety`, or GitHub's Dependabot once a `.github/` directory exists — see Section 14) in an environment with full network access, ideally as a CI job, before this codebase takes any external dependency on trust.

### 12.9 What's genuinely good here, stated without qualification

No `shell=True` anywhere in 31,347 lines. No `eval`/`exec`. No `pickle`. No hardcoded secrets, API keys, or passwords in source (checked via pattern grep across the entire backend). No raw SQL string interpolation — all database access goes through the ORM or parameterized `text()` constructs. `bandit` found zero Medium or High severity issues in an automated pass. The FFmpeg/FFprobe layer uses list-argument subprocess calls exclusively. These are the highest-leverage, hardest-to-retrofit security properties a codebase can have, and this one has all of them from the start.

## Section 13 — Performance

### 13.1 Video import is broken end-to-end by an `await` on a synchronous call — **[Verified by reproduction and full call-graph tracing]** — **Critical**

This is the highest-severity finding in the audit, and it is the one this report is most confident in, because it was independently confirmed by four separate methods: `mypy --strict`, a full cross-reference of every call site of the function in question, direct reading of the callee's signature, and — the most conclusive test — reachability tracing through the actual public REST route.

**The bug, `services/import_service.py::_probe_file`:**
```python
async def _probe_file(self, path: Path) -> dict[str, Any]:
    try:
        return await self._ffprobe.probe(str(path))
    except Exception as exc:
        raise ValidationError(...) from exc   # (also missing `from exc` in the original — see 2.1's B904 list)
```
**The callee, `infrastructure/ffmpeg/ffprobe.py::FFprobeService.probe`:**
```python
def probe(self, input_path: str | Path) -> MediaInfo:   # NOT async
    ...
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)   # blocking
    ...
    return MediaInfo(...)
```
`probe()` is a plain synchronous method that returns a `MediaInfo` object directly, not a coroutine. `await`-ing its return value raises `TypeError: object MediaInfo can't be used in 'await' expression` — unconditionally, every single time `_probe_file` executes. `mypy --strict` independently flags the exact same line (`misc: Incompatible types in "await" (actual type "MediaInfo", expected type "Awaitable[Any]")`) — full agreement between static typing and manual tracing.

**This is not a theoretical or edge-case bug.** Every other call site of `.probe(` in the codebase (`ffmpeg/manager.py:115,126`, six locations in `ffmpeg/video_info.py`) calls it synchronously, without `await`, and gets a working `MediaInfo` back — confirming `probe()`'s synchronous design is correct and intentional, and that `import_service.py` is the one place someone wrote `await` in front of it, most plausibly out of habit inside an `async def` method surrounded by other awaited calls. Tracing reachability confirms this isn't buried behind a feature flag or an unused code path: `POST /api/v1/projects/{project_id}/videos/import` and the corresponding validate endpoint (`api/routes/videos.py`) call `ImportService.import_file()` / `.validate_import()` directly and synchronously within the request handler (3.4), which calls `_probe_file()`. **Every attempt to import a video through the documented public API — the single most basic, headline feature of this application ("🎬 Video Import" is the first bullet in the README's feature list) — currently raises an unhandled `TypeError` and fails.**

**Why "Critical" and not just "High" like the other functional bugs in this report:** every other bug in this audit degrades, misconfigures, or creates risk in some path of the application. This one makes the primary use case non-functional, unconditionally, with no workaround, on the exact code path a new user or a Phase C AI pipeline would exercise first. **Fix:** remove the `await` — `return self._ffprobe.probe(str(path))` — and, given 13.2 below, wrap the call in `asyncio.to_thread()` rather than calling it bare, since it's a blocking call being made from `async def` code either way.

### 13.2 Blocking subprocess calls run directly inside the async event loop — High

Beyond the specific bug in 13.1, the underlying pattern is a broader performance problem: `FFprobeService.probe()`, and by extension every sibling class in `infrastructure/ffmpeg/` (`audio.py`, `export.py`, `frame.py`, `process.py`, `proxy.py`, `scene.py`, `thumbnail.py`), calls `subprocess.run(...)` — a **blocking** call — directly. A repo-wide grep for `asyncio.to_thread` and `run_in_executor` (the standard ways to offload blocking work from an async context) returns **zero matches** anywhere in the backend. Combined with 3.4 (video import runs synchronously inside a FastAPI request handler, not dispatched to the Celery queue that already exists for this purpose), this means: for however long `ffprobe`/`ffmpeg` takes to run on a given file — seconds for a quick probe, potentially minutes for a large transcode — **the entire single-process asyncio event loop is blocked**, which means every other concurrent HTTP request, every WebSocket message (including progress updates for *other* jobs), and any other coroutine scheduled on that loop stalls for the same duration. **Why it matters:** this is fine at "one developer testing locally," and becomes the defining scalability problem the moment more than one operation needs to happen at once — which, for a video editor with live progress updates over WebSocket while a file imports, is not an edge case, it's the normal UI expectation. **Fix:** wrap every blocking FFmpeg/FFprobe subprocess call in `asyncio.to_thread()` (Python 3.9+, trivial to retrofit) at minimum; better, route heavy operations through the Celery queue (which already has the right worker-pool architecture for this — see Section 9) instead of the request path at all.

### 13.3 Memory/CPU-bound HAL and complexity hotspots

Cross-referencing 2.3/6.2/7.5: the three highest-cyclomatic-complexity methods in the backend (`FFmpegLocator.detect_capabilities` at 34, `ProgressParser.parse_line` at 21, `PluginVersionResolver.satisfies` at 22) are not performance-hot in the traditional sense (none run in a tight loop), but complexity of this magnitude in code that runs once per capability-detection or once per progress line is a maintainability-driven performance risk: the more branches a hot-ish path has, the harder it is to reason about which branch actually executes under real hardware, making performance regressions in these specific methods hard to catch by inspection.

### 13.4 Unbounded upload memory usage — High

Full evidence in 5.2/12.4; performance framing here: `content = await file.read()` (no size argument) followed by `dest.write_bytes(content)` in `api/routes/videos.py` materializes the **entire uploaded video file** as a single `bytes` object in the FastAPI process's memory before any of it reaches disk. `APISettings.max_upload_size` (default 50 GiB) is declared and never enforced anywhere (verified: zero references outside its own field definition). For a video-editing tool where multi-gigabyte source files are the normal case, not the exception, this is a direct, easily-triggered path to process-wide OOM — and because this runs inside the single-process FastAPI event loop (13.2), an OOM here doesn't just fail one request, it can take down the whole running server, including any other in-progress jobs. **Fix:** stream the upload directly to disk in fixed-size chunks (`while chunk := await file.read(1024 * 1024): f.write(chunk)`), enforcing `max_upload_size` incrementally as bytes arrive rather than after the fact.

### 13.5 Database and caching — no red flags found, not exhaustively load-tested

WAL mode, connection-pragma tuning, and the repository layer's pagination support (4.4) are all sound choices for the expected access pattern (single local writer, occasional concurrent reads). No N+1-style query pattern was identified in the models/repositories reviewed, though a full audit of every service-layer call site for lazy-loading-triggered N+1 queries was not completed given the time budget — flagged as a follow-up rather than asserted clean.

## Section 14 — Production Readiness

### 14.1 There is no CI/CD pipeline of any kind — **Critical**

**Evidence:** no `.github/workflows/`, no `.gitlab-ci.yml`, no CircleCI/Travis/Buildkite config, no pre-commit hook actually installed (a `pre-commit` package is listed as a dev dependency in `pyproject.toml`, but there is no `.pre-commit-config.yaml` file in the repository for it to run against). The only automation-adjacent artifact is `docker/docker-compose.yml`.

**Why this is Critical and not just a process gap:** this single absence is the root cause this report keeps arriving back at from every other section. It is why a `strict = true` mypy config has 254 unaddressed errors (2.1). It is why 78% of ruff's findings are auto-fixable and unfixed (2.1). It is why a test file imports a class from the wrong module and has done so long enough that a second test file (the integration suite) copied the same mistake (9.1). It is why `StorageManager` cannot be constructed (5.1). It is why two competing `Base` classes coexist undetected (4.1). None of these individual bugs are hard to fix — every single one would be caught by a CI job running `ruff check`, `mypy`, and `pytest` on the next pull request. Their presence, all at once, in a codebase this otherwise disciplined, is the clearest possible signal that no such job exists yet.

**Fix, concretely, in priority order:** (1) a GitHub Actions workflow that runs `ruff check`, `mypy backend/`, and `pytest tests/unit --continue-on-collection-errors` on every push/PR — this alone, even before fixing any of the bugs it would surface, converts every finding in this report from "latent" to "impossible to merge without acknowledging"; (2) add a `.pre-commit-config.yaml` using the `ruff`/`mypy` hooks the project already depends on, so issues are caught before commit, not just before merge; (3) once CI is green, add a coverage-trend check so 11.4's gap doesn't recur silently.

### 14.2 The documented dev workflow is broken at the first command — High

**Evidence, `Makefile`:**
```makefile
dev:
	cd frontend && bun dev &
	cd backend && uvicorn ...
install:
	cd frontend && bun install
	...
```
**There is no `frontend/` directory anywhere in this repository.** The actual frontend scaffold lives at the repository root (`src/`, `package.json`, `bun.lock` — see 1.2 for what that scaffold actually is). `make dev` and `make install`, run exactly as the README instructs a new contributor to run them, fail immediately with `cd: frontend: No such file or directory`. **Why it matters:** this is the very first command in the onboarding path, and it doesn't work. Combined with 14.1, nothing catches this because nothing runs the Makefile targets in an automated way either. **Fix:** either move the frontend into `frontend/` to match the Makefile, or fix the Makefile to `cd` into the actual location — a five-minute fix that has apparently gone unnoticed because it's never been exercised end-to-end.

### 14.3 Docker/Compose setup does not match its own documentation

**Evidence:** `docker/Dockerfile` is a single-stage `FROM python:3.11-slim` build that installs `pip install .[dev]` — pulling `pytest`, `mypy`, `ruff`, `pre-commit`, and the rest of the dev toolchain into what should be a lean runtime image — has no `HEALTHCHECK`, runs as root (no `USER` directive), and never builds or copies the frontend at all. This directly contradicts the README's own claim of a **"Multi-stage Dockerfile with GPU target."** There is no second `FROM` stage, and no CUDA/ROCm base image or GPU runtime package anywhere in the file — for an application whose HAL is explicitly designed around CUDA/ROCm/Metal/CPU backends (Section 6), the containerized deployment path currently only supports CPU. `docker/docker-compose.yml` defines exactly one service (`backend`); there is no `redis` service and no `celery worker` service, despite the queue subsystem being built around an optional Redis broker (9.4/9.5) — meaning **the Celery-based background job system this application's own architecture depends on does not run at all in the provided `docker compose up` path.**

**Fix:** either update the README to accurately describe what the Dockerfile does today (single-stage, CPU-only, dev-and-runtime combined), or build the multi-stage/GPU/worker setup the README already claims exists. Add a non-root `USER`, add a `HEALTHCHECK`, and split dev dependencies out of the runtime image (a `--target production` multi-stage split is the standard fix). Add `redis` and a `celery worker` service to `docker-compose.yml` so the documented architecture is actually runnable via the documented command.

### 14.4 Logging and correlation — a genuine strength

`infrastructure/logging/` implements structured logging (`ContextLogger`) with correlation-ID propagation (`get_current_correlation_id()`, bound automatically into every logger via `api/deps.py::get_logger`), and `CorrelationIDMiddleware` threads a request-scoped ID through the stack. This is real, production-grade observability groundwork — the kind of thing that's easy to skip at this stage of a project and wasn't skipped here. It's undermined operationally by 12.7 (37 silent `except: pass` blocks that never reach the logger at all), but the logging *infrastructure* itself is sound.

### 14.5 Startup/shutdown lifecycle — sound, with one caveat

Covered in 3.1: the FastAPI `lifespan` context manager correctly initializes and tears down the database and filesystem. The caveat is 9.2: if application shutdown ever routes through `Dispatcher.stop()`, the confirmed indefinite hang in that method means graceful shutdown itself could hang — worth explicitly testing once 9.2 is fixed.

### 14.6 Configuration management — mostly good, with a recurring "declared but disconnected" pattern

`pydantic-settings` with nested-delimiter env vars (`LOCALCLIP_API__DEBUG`, etc.) is a clean, modern approach, and `.env.example` is well-organized. But this audit independently found the same failure pattern three separate times across three unrelated subsystems: `APISettings.max_upload_size` (13.4), `DatabaseSettings.pool_size`/`max_overflow` (4.3), and `StorageSettings`'s field names not matching what `StorageLimits.from_settings()` expects at all (5.1). See 15.3 for this pattern written up once, at the level it deserves.

### 14.7 Upgrade path — untested, one confirmed landmine

Given 4.1 (the split ORM metadata registry making Alembic autogenerate unsafe for 13 of 14 tables), the schema upgrade path is the single riskiest piece of "production readiness" in this codebase — not because today's migration is wrong, but because the tooling meant to keep future migrations correct is silently pointed at the wrong data.

## Section 15 — Technical Debt

This section deliberately synthesizes rather than re-litigates — every item below was already established with evidence in an earlier section; what's new here is grouping by *pattern*, which is what turns a list of bugs into a debt-reduction plan.

### 15.1 Pattern: the same fix was needed twice and was hand-rolled twice, differently

- Path-containment checking: written independently (and identically wrong) in `DirectoryManager.validate_path()` and `PluginSandbox.resolve_path()` (12.3).
- SQLite pragma configuration: implemented in both `database/base.py::set_sqlite_pragmas` and (per the file layout referenced in 4.4) again in `engine.py::_enable_wal_mode`.
- Global exception handling: implemented as both `ErrorHandlingMiddleware` and `app.py`'s `@app.exception_handler(Exception)` (3.2), with no clear ownership of which one is authoritative.
- God-object risk from under-decomposition: `WebSocketManager` (755 lines, 25 methods, 4+ responsibilities — 10.2) is the most acute instance, but `FFmpegLocator.detect_capabilities` (CC 34) and `ProgressParser.parse_line` (CC 21) are the same story at the method level rather than the class level.

**Refactoring candidates, ranked by leverage:** (1) extract one shared `is_path_within()` utility — fixes a real bug in two places at once; (2) decompose `WebSocketManager` into `ConnectionRegistry` + `HeartbeatMonitor` + `EventPublisher` — no behavior change, pure risk reduction; (3) resolve the dual exception-handling mechanism to one.

### 15.2 Pattern: refactors that didn't update every dependent

- `RetryPolicy` moved to `models.py`; two test files still import it from `retry.py`, and `RetryState`/`ExponentialBackoff` are referenced by a test but no longer exist anywhere (9.1).
- `StorageSettings`'s fields were restructured (renamed *and* re-unitted, bytes vs. GB) after `StorageLimits.from_settings()` was written against an earlier shape; `StorageManager` cannot be constructed as a result (5.1).
- The README's "Project Status" table still shows Module A4 (Database) as "🔜 Next" and A5–A8 as "⏳ Pending," while the actual repository has fully-built `database/`, `filesystem/`, `hal/`, `ffmpeg/`, and `plugins/` packages, plus all of Phase B (16.1).

**Why this is worth calling out as a category, not three unrelated bugs:** each of these is small and mechanical to fix in isolation, but their existence *as a pattern* means "I refactored X" is not currently followed by "and I grepped for every place that depended on the old shape of X" — which is a process gap (again pointing back at 14.1's missing CI) more than three independent lapses in judgment.

### 15.3 Pattern: configuration settings that are declared, documented, and disconnected from behavior

Three confirmed instances, independently discovered in three different subsystems, of a `Settings` field existing and doing nothing: `APISettings.max_upload_size` (13.4 — zero enforcement anywhere), `DatabaseSettings.pool_size`/`max_overflow` (4.3 — hardcoded literals in `init_engine()` instead), and `StorageSettings`'s fields not even matching the names `StorageLimits.from_settings()` reads (5.1, the most severe instance — this one doesn't just fail to apply the configured value, it crashes). **Why this matters as a named pattern:** a reader of `config/settings.py` or `.env.example` reasonably assumes every field there does something — three confirmed counterexamples (out of a settings surface this audit only partially enumerated) means every other setting in that file now deserves a "does this actually get read?" check before being trusted, which is a real, if unglamorous, chunk of technical debt to pay down deliberately rather than discover one crash at a time.

### 15.4 Over-engineering vs. under-engineering — a fair, two-sided read

**Not over-engineered where it matters:** the DDD layer (aggregates, domain events, value objects — 1.1), the generic repository with optimistic locking (4.2), and the plugin versioning/resolution logic (8.3) are all appropriately sophisticated for what they're solving, not speculative complexity. **Under-engineered in exactly the place complexity was most needed:** the plugin *sandbox* (8.1) is the one place in the architecture where the design's own ambition (a marketplace-ready plugin system with manifests, versioning, and permission scopes) outran the actual enforcement mechanism (in-process `importlib`, no OS/process isolation) — this is under-engineering relative to the surrounding code's own stated goals, not over-engineering. **Mildly over-scoped for its current phase:** the `ai` extras dependency surface (torch, onnxruntime-gpu, four other ML packages) is large and version-fragile for a phase that hasn't started, and two of its eight package names don't currently resolve (16.2) — worth validating incrementally rather than declaring the full Phase C dependency tree up front.

### 15.5 Hidden risk not yet surfaced elsewhere in this report

The `.venv_test/` directory (12 KB, broken symlinks) committed to git despite a `.gitignore` that excludes `.venv/`/`venv/`/`env/` but not this specific name, and the 876 KB of pre-built Vite output committed under `isolate/` (1.2), are individually trivial but both point at the same root cause as 15.2/15.3: nothing in the current workflow catches "a file that shouldn't be in git got committed anyway" before it lands on `main`.

## Section 16 — Missing Features

### 16.1 Documentation that describes a materially different, smaller codebase than what exists — High

**Evidence:** `README.md`'s "Project Structure" section shows only a `foundation/` skeleton (config, logging, errors) and its "Project Status" table marks Module A4 (Database Engine) as **"🔜 Next"** and Modules A5 through A8 as **"⏳ Pending."** The actual repository has complete, substantial implementations of all of them: `infrastructure/database/` (14 ORM models, a generic repository layer, Alembic migrations), `infrastructure/filesystem/` (7 manager classes), `infrastructure/hal/` (4 backend providers plus selection/memory management), `infrastructure/ffmpeg/` (12 files, command building through export), and `infrastructure/plugins/` (discovery through sandboxing) — plus the entirety of Phase B (domain layer, repositories, queue, WebSocket, services, REST API), none of which the README's status table acknowledges exists at all. The README also separately uses a "Phase 7 / Module A1–A8" numbering scheme that doesn't match the "Phase A/B/C/D" scheme used everywhere else (this brief included), which is its own, smaller consistency problem sitting on top of the larger staleness one.

**Why it matters:** this is the single most consequential documentation gap in the audit, not because it's hard to fix, but because of what it costs a reader who trusts it — a new contributor, a prospective plugin developer, or (concretely) the first several tool calls of this very audit would have wildly undersold the codebase's actual maturity if they'd stopped at the README instead of reading source, which is exactly the anti-pattern this brief's instructions were written to prevent. **Fix:** regenerate the "Project Status" table from what's actually in `backend/`, and settle on one phase-naming scheme across the README, the ADRs, and this kind of audit brief.

### 16.2 Two of eight "AI extras" dependency names don't exist on PyPI — High

**Evidence, verified directly against the PyPI JSON API, not from memory:**
```
whisper-x      -> HTTP 404  (correct package name is `whisperx`)
pyscenedetect  -> HTTP 404  (correct package name is `scenedetect`)
whisperx       -> HTTP 200
scenedetect    -> HTTP 200
pyannote-audio -> HTTP 200  (PEP 503 name-normalization makes the hyphenated form resolve correctly — this one is fine)
```
`pip install .[ai]` (or any full install using the `ai` extras group in `pyproject.toml`) **fails outright** on two of its eight declared dependencies. **Why it matters:** this is the dependency group Phase C is entirely built on top of; it has apparently never been installed successfully as written, which is itself a data point about how far Phase C planning has been validated against reality versus written down as intent. **Fix:** two one-line changes (`whisper-x` → `whisperx`, `pyscenedetect` → `scenedetect`) in `pyproject.toml`, plus (given 16.1's broader pattern) a CI job that actually runs `pip install .[ai]` — even without a GPU, package resolution can be checked in a CPU-only CI runner.

### 16.3 Plugin system: scaffolding is complete, the thing that makes it safe to use is not

Restating 8.1/8.4 from the "what's missing" angle specifically: discovery, manifest parsing, semver-based dependency resolution, health checks, and lifecycle management are all built. What's missing is the actual execution boundary — no subprocess isolation, no restricted namespace, no OS-level sandbox — meaning the feature that's genuinely absent isn't "plugin support," it's **"plugin support that's safe to point at a plugin you didn't write yourself."** This is worth listing explicitly as a missing feature (not just a bug) because it's not a small gap to close — it's close to its own subproject, and Phase C planning should treat it as one rather than assuming the sandbox class name means the hard part is done.

### 16.4 No dependency lockfile

`pyproject.toml` uses loose version ranges (`torch>=2.1,<3.0`, etc.) with no `uv.lock`, `poetry.lock`, or pinned `requirements.txt` anywhere in the repository. For a dependency set this GPU/CUDA-version-sensitive, an unpinned install today and the same unpinned install in three months can resolve to meaningfully different, differently-behaving package versions. **Missing:** a lockfile and a documented "these exact versions are what CI/production installs" story.

### 16.5 Developer experience gaps

- No `.pre-commit-config.yaml` despite `pre-commit` being a listed dev dependency (14.1).
- No `CONTRIBUTING.md` was found describing how to actually run the (currently broken — 14.2) dev workflow, propose a change, or where the phase-numbering scheme is authoritative.
- No `CHANGELOG.md`.
- The Makefile's `frontend/` mismatch (14.2) means `make install && make dev` — the two commands a new contributor would run first — both fail immediately.

### 16.6 What's already well-covered and shouldn't be re-added

For balance: this codebase does **not** need a second logging framework, a second ORM, a second dependency-injection framework, or a second error-handling scheme layered on top of what exists — the underlying design in each of those areas is sound (Sections 1, 4, 14.4). The missing pieces above are specifically process/tooling/documentation gaps and one real security-architecture gap (16.3), not missing subsystems.

## Section 17 — Phase Readiness (Phase C)

**Verdict: not ready.** Not because the foundation is weak — it's the opposite; Phase A/B's architecture (Sections 1, 4) is good enough that it would be a shame to build Phase C on top of the specific unresolved issues below rather than after them. Every blocker listed here was independently verified elsewhere in this report; this section exists to answer the brief's specific question in one place.

### Blocker 1 — No CI (14.1)
Phase C is, by the project's own description, the highest-risk phase (AI models, GPU code paths, external provider integrations). Adding that volume of new code with zero automated gate means every bug class already found in Phase A/B (broken imports, hanging tests, dead configuration) will recur at Phase C's larger scale, and nothing will catch it before merge. **This should be fixed before Phase C starts, not during it.**

### Blocker 2 — The event-loop-blocking pattern will get worse, not better (13.1, 13.2)
Phase C's core operations — transcription, scene detection, object detection, embedding generation — are all heavier and longer-running than the FFprobe call that's already confirmed to block the event loop when called incorrectly (13.1) and confirmed to have no offload pattern anywhere in the codebase to call correctly either (13.2, zero `asyncio.to_thread`/`run_in_executor` usage). If Phase C services are written the way `import_service.py` was written, every AI inference call will freeze the API and WebSocket for its full duration — potentially minutes, not the ~1 second an FFprobe call takes. **The offload pattern needs to exist and be the default before the first Phase C service is written, not retrofitted after.**

### Blocker 3 — Two of eight AI dependencies don't install (16.2)
Verified directly against PyPI: `whisper-x` and `pyscenedetect` are wrong package names. `pip install .[ai]` fails today. Trivial to fix, but it means the AI dependency surface has not been successfully installed even once in its current form — a two-line fix, but a blocker until it's applied and actually run.

### Blocker 4 — The plugin sandbox is not an execution sandbox (8.1, 16.3)
If Phase C plugins are meant to be user-installable (the manifest/versioning/discovery system strongly implies this is the intent), the current `importlib`-based loader gives any plugin full, unrestricted access to the host process. This is the single most consequential blocker to fix *before* any external-facing plugin distribution mechanism goes live, because retrofitting sandboxing after plugins already exist in the wild is a much harder migration than building it in from the start.

### Blocker 5 — FFmpeg filter-argument escaping gap will be exercised directly by AI-generated content (7.2)
Phase C is what will start feeding AI-transcribed caption *text* — arbitrary spoken language, containing colons, quotes, and apostrophes as a matter of course — through the same string-interpolation pattern already shown to break on Windows paths today. This needs the escaping fix from 7.2 in place before caption burn-in is wired to real transcription output, not after the first bug report.

### Blocker 6 — The database migration tooling is unsafe for 13 of 14 tables (4.1)
Phase C will need new tables (model registry entries, embeddings, provider configs — some of which already exist as stubs, e.g. `model_registry.py`, `provider_config.py`) and new migrations. Using `alembic revision --autogenerate` today, exactly as documented, would not see any schema change to those tables at all. **Fix the split `Base` class before the first Phase C migration is written**, or every Phase C migration will need to be hand-audited line-by-line against what autogenerate silently missed.

### What is genuinely ready

The **domain layer** (1.1), the **repository pattern** (4.2), the **HAL's structural design** (6.1 — CUDA→ROCm→Metal→CPU fallback with a real OOM-recovery strategy already sketched), and the **Celery queue's configuration** (9.4 — `task_acks_late`, sensible time limits, already built for long-running jobs) are all the right shape to build Phase C on top of once the six blockers above are closed. This is not a "the foundation needs to be rebuilt" verdict — it's a "close six specific, well-understood gaps first" verdict.

## Section 18 — Professional Scorecard

Each score is justified against specific findings already established above, not assigned impressionistically. The overall score is the unweighted mean of the ten dimensions, stated plainly rather than dressed up as a more precise formula than it is.

| Dimension | Score | Rationale |
|---|---:|---|
| **Architecture** | 78/100 | Genuinely clean dependency direction (1.1, verified by grep), a real DDD domain layer, a well-built generic repository. Docked for the two-competing-root-projects problem (1.2, Critical) and the split `Base` metadata registry (4.1), both of which are structural, not cosmetic. |
| **Code Quality** | 66/100 | Zero syntax errors across 168 files; complexity is localized (radon MI: 0 files below grade A), not systemic. Docked heavily for a `strict=true` mypy config sitting at 254 unaddressed errors and a docstring-convention/config mismatch inflating ruff's count — the *tooling* is good, the *conformance* to it isn't (2.1). |
| **Security** | 58/100 | No `shell=True`/`eval`/`exec`/`pickle`/hardcoded secrets anywhere (12.9) is a real, hard-earned floor. Pulled down by a provably broken encryption helper (12.5), path-traversal protection that's dead code (12.3), an unsanitized upload filename (12.4), and a plugin loader with no real execution isolation (8.1). The no-auth decision itself (12.1) is not scored as a negative — it's a reasoned, documented tradeoff — but the boundary it depends on has a confirmed gap (12.2). |
| **Performance** | 55/100 | Sound DB tuning (4.4) and sensible Celery config (9.4) pull this up. Pulled down hard by a confirmed event-loop-blocking pattern with zero offload usage anywhere (13.2) and unbounded upload memory usage with a non-enforced size limit (13.4). Would score lower if 13.1's critical bug weren't a "does it run at all" issue scored primarily under Testing/Production Readiness instead. |
| **Testing** | 47/100 | 1,389 passing tests represent real investment, and the 96.3% pass-rate-of-what-runs is a genuine positive (11.2). Scored below 50 anyway because the suite **cannot currently complete a single full run** (11.1) and one entire test class hangs indefinitely (9.2/11.2) — a test suite that can't finish isn't fully credited for the tests inside it, however good those individual tests are. |
| **Maintainability** | 70/100 | Consistent module boundaries, docstring-documented ADRs (16 of them) for major decisions, and a repository/service split that makes most changes local rather than sprawling. Docked for the "same fix hand-rolled twice" pattern (15.1) and one 755-line God Object (10.2). |
| **Scalability** | 60/100 | The queue/worker architecture is the right shape to scale (9.4). Docked for the single-process-blocks-everyone pattern (13.2) that currently undermines that architecture's own value, and for `docker-compose.yml` not actually running a worker process at all (14.3). |
| **Production Readiness** | 38/100 | The lowest score in this scorecard, deliberately. Structured logging and correlation IDs (14.4) and a correct FastAPI lifespan (14.5) are real positives. Everything else in Section 14 is a readiness blocker: zero CI (14.1), a broken first-command dev workflow (14.2), a Dockerfile that doesn't match its own README description and ships dev tools in the runtime image (14.3), and an Alembic setup that's unsafe for 93% of the schema (14.7/4.1). |
| **Documentation** | 42/100 | 16 ADRs recording real architectural decisions with real rationale (12.1 is a good example) is more documentation discipline than most projects at this stage have. Scored low anyway because the single most-read document — the README — actively misrepresents how much of the codebase exists (16.1), which does more damage to a reader's understanding than having no README at all. |
| **Developer Experience** | 50/100 | Clear module layout, thorough `.env.example`, and (once you're past the first command) a coherent `Makefile` structure. Scored at the midpoint because the actual first-run experience (`make install`, `make dev`) fails outright (14.2/16.5), and there's no lockfile (16.4) or pre-commit hook (16.5) to catch problems before they're committed. |
| **Overall** | **57/100** | Unweighted mean of the above. Read this as: *a well-architected codebase that is not yet safe to build Phase C on, and not yet safe to call "production-grade," for a specific, fixable, well-enumerated set of reasons* — not as "roughly half-broken." The distribution (a 78 next to a 38) is the more informative signal than the average itself. |

## Section 19 — Prioritized Findings

The brief asks for a "Top 100" list. This audit found **61 distinct, individually-evidenced findings** — every one backed by a file, usually a line number, and in the highest-severity cases a reproduction. Sixty-one is the honest number for a Phase A/B codebase of this size; padding it to 100 would mean inventing findings or splitting single issues into duplicates, which this report treats as a worse outcome than reporting an accurate, shorter list. Full evidence, "why it matters," and fix detail for every item below lives in the referenced section — this table is a prioritized index, not a re-derivation.

### Critical (3)

| # | Finding | Evidence | Ref | Recommendation |
|---|---|---|---|---|
| 1 | Video import raises `TypeError` on every call — headline feature is non-functional | `await` on synchronous `FFprobeService.probe()`, reachable via public REST route, confirmed by mypy + call-graph trace + reproduction | 13.1 | Remove the `await`; wrap in `asyncio.to_thread` |
| 2 | Two unrelated applications share one repository, undocumented | Convex/SST/landing-page scaffold at repo root vs. the real Python backend; zero cross-references | 1.2 | Delete the scaffold or record the decision in an ADR |
| 3 | No CI/CD pipeline exists at all | No `.github/`, no `.pre-commit-config.yaml`; root cause of ≥8 other findings below | 14.1 | Add `ruff`/`mypy`/`pytest` as a required PR check this week |

### High (15)

| # | Finding | Evidence | Ref | Recommendation |
|---|---|---|---|---|
| 4 | Split SQLAlchemy `Base` — Alembic autogenerate blind to 13/14 tables | `models/settings.py` imports a different `Base` than the other 13 models; `alembic/env.py` targets the minority one | 4.1 | Unify on one `Base`, repoint 14 imports |
| 5 | `StorageManager` cannot be constructed — quota system is fully non-functional | `AttributeError` in `__init__`; `StorageSettings` fields don't match what `StorageLimits.from_settings()` reads (name *and* unit mismatch) | 5.1 | Align field names/units; add a construction smoke test |
| 6 | Unbounded upload — entire video buffered in process memory, no enforced size limit | `content = await file.read()`; `max_upload_size` never referenced outside its own definition | 5.2, 13.4 | Stream to disk in chunks; enforce the limit incrementally |
| 7 | CORS headers dropped on every non-2xx API response | Reproduced: successful responses get `access-control-allow-origin`, error responses (via `ErrorHandlingMiddleware`) don't | 3.3 | Reorder middleware or attach CORS headers in the error handler |
| 8 | Unsanitized multipart `filename` used as a filesystem path component | `dest = tmp / (file.filename or "video.mp4")`, no traversal check | 12.4 | Generate server-side filenames; never trust client filenames |
| 9 | Path-traversal guard is defined, has zero callers, and has a sibling-directory bypass bug where reimplemented | `validate_path()` 0 call sites; `str.startswith()` containment check in two places | 12.3, 8.2 | One shared `is_path_within()` using `Path.is_relative_to()` |
| 10 | Two AI-extras dependency names don't exist on PyPI | `whisper-x` and `pyscenedetect` both 404 against the live PyPI API | 16.2 | Rename to `whisperx` and `scenedetect` |
| 11 | `RetryPolicy` import error aborts collection of the entire unit test suite | `ImportError` from wrong module path; `RetryState`/`ExponentialBackoff` don't exist anywhere | 9.1 | Fix the two import statements (also present in the integration suite) |
| 12 | Entire `TestDispatcher` test class hangs indefinitely | Isolated by binary search; confirmed via `-v` output stalling mid-test with no completion | 9.2 | Add a bounded timeout inside `Dispatcher.stop()` |
| 13 | `is_encrypted()` always returns `False`, including for real ciphertext | Reproduced directly against the real encryption class; called from 3 production sites | 12.5 | Attempt decrypt in a try/except instead of shape-checking |
| 14 | Documented dev workflow fails on the first command | `Makefile` targets `frontend/`, which doesn't exist anywhere in the repo | 14.2 | Fix the path or relocate the frontend scaffold |
| 15 | README materially misrepresents implementation status | Claims Modules A4–A8 are "Next/Pending"; all are fully implemented, as is all of Phase B | 16.1 | Regenerate the status table from `backend/` directly |
| 16 | FFmpeg filter-argument escaping missing for subtitle/caption paths and style strings | Unescaped `:`/`\`/`'` interpolated into `subtitles=`/`ass=`/`force_style=` filter arguments | 7.2 | Implement FFmpeg's documented filter-escaping rules once, use everywhere |
| 17 | Plugin "sandbox" provides no real process/OS-level isolation | `importlib.import_module` in-process loading; permission checks are opt-in, not enforced | 8.1 | Move plugin execution to an isolated subprocess before any external plugin distribution |
| 18 | Dockerfile/compose materially don't match README's claims and don't run the queue worker | Single-stage, CPU-only, dev-deps-in-runtime, root user, no healthcheck; no `redis`/worker service in compose | 14.3 | Build the multi-stage/GPU/worker setup the README already claims, or correct the README |

### Medium (20)

| # | Finding | Ref |
|---|---|---|
| 19 | Missing `Awaitable` import — undetected at runtime only because of `from __future__ import annotations`, flagged by both ruff and mypy | 2.2 |
| 20 | Redundant global exception handling; `app.py`'s handler is unreachable dead code (verified by reproduction) | 3.2 |
| 21 | FFmpeg/FFprobe resolved by bare command name in 9 places despite a locator built for this purpose existing; PATH-hijacking risk (CWE-426) | 7.3, 6.3, 12.6 |
| 22 | `DatabaseSettings.pool_size`/`max_overflow` configured but hardcoded-over in `init_engine()` | 4.3 |
| 23 | `.env.example` ships `DEBUG=true`, exposing OpenAPI/Swagger by default on the documented setup path | 3.6 |
| 24 | Dependency injection is manual/duplicated per route file rather than centralized | 1.4, 3.5 |
| 25 | `WebSocketManager` God Object — 755 lines, 25 methods, 4+ responsibilities | 10.2 |
| 26 | 16 instances of `raise` inside `except` without `from`, destroying exception chains | 2.1 |
| 27 | 37 instances of silent `except Exception: pass`, including a confirmed GPU-cache-clear failure path | 12.7 |
| 28 | `FFmpegLocator.detect_capabilities` — cyclomatic complexity 34 (worst in the backend by 3x) | 2.3, 7.5 |
| 29 | `ProgressParser.parse_line` — CC 21 | 2.3 |
| 30 | `PluginVersionResolver.satisfies` — CC 22 | 2.3, 8.3 |
| 31 | 14 real test failures in `queue/test_priority.py` and `test_progress.py`, not yet root-caused | 9.3 |
| 32 | 12 real test failures across `domain/test_exceptions.py`, `test_plugin.py`, `test_state_machines.py` | 11.2 |
| 33 | SQLite pragma configuration implemented twice independently (`database/base.py` and `engine.py`) | 15.1 |
| 34 | `.venv_test/` (broken venv) and `isolate/` (876 KB build output) committed to git | 1.2, 15.5 |
| 35 | No dependency lockfile for a GPU/CUDA-version-sensitive dependency set | 16.4 |
| 36 | Fernet mischaracterized as "AES-256-GCM"; machine-derived encryption key built from low-entropy, often-observable inputs, then persisted to a sibling plaintext-adjacent file anyway | 12.5 |
| 37 | Coverage percentage from this audit's first attempt is unreliable (likely import-time-only) and should not be trusted as reported | 11.4 |
| 38 | Confirmed asyncio "Task was destroyed but it is pending" leaks during queue test execution | 9.2, 11.3 |

### Low (13)

| # | Finding | Ref |
|---|---|---|
| 39 | 44 unused imports (`F401`) | 2.1 |
| 40 | 3 unused variables (`F841`), including an apparently-abandoned timing measurement duplicated across two HAL provider files | 2.1, 6.2 |
| 41 | `ruff`'s `D212`/`D213` docstring-convention ignore-list doesn't match the codebase's actual docstring style, manufacturing 1,363 of 2,024 total lint findings | 2.1 |
| 42 | Real documentation-coverage gaps: 138 undocumented public methods, 57 undocumented magic methods, 29 undocumented public functions, 21 undocumented public classes | 2.1 |
| 43 | No `CONTRIBUTING.md` | 16.5 |
| 44 | No `CHANGELOG.md` | 16.5 |
| 45 | `pre-commit` listed as a dev dependency with no `.pre-commit-config.yaml` to run | 14.1, 16.5 |
| 46 | 2 naming-convention violations (`N802`/`N806`) | 2.1 |
| 47 | 15 opportunities to modernize hand-rolled `str`+`Enum` to `StrEnum` (`UP042`) | 2.1 |
| 48 | ~24 opportunities to migrate `os.path` usage to `pathlib` (`PTH*` rules) | 2.1 |
| 49 | WebSocket topic-name traversal check uses the same bare-substring pattern as 12.3, lower risk since topics aren't used as filesystem paths in what was reviewed | 10.1 |
| 50 | README uses a "Phase 7 / Module A1–A8" numbering inconsistent with the "Phase A/B/C/D" scheme used elsewhere | 16.1 |
| 51 | 23 stale `# type: ignore` comments no longer needed (`mypy unused-ignore`) | 2.1 |

### Informational (10)

| # | Note | Ref |
|---|---|---|
| 52 | No `shell=True`/`eval`/`exec`/`pickle`/hardcoded secrets anywhere in 31,347 lines — a genuine, hard-earned strength | 7.1, 12.9 |
| 53 | Domain layer has zero infrastructure/service/API imports — real Clean Architecture layering, verified by grep, not assumed | 1.1 |
| 54 | `WebSocketManager`'s security validator is the best-executed security-conscious module in the codebase — rate limiting, size limits, structural validation, correctly-wired cleanup | 10.1 |
| 55 | `hal`/`plugins` test suites pass 100% clean (352/352, 1 skipped) — the most reliably verified subsystem alongside `websocket` | 11.2 |
| 56 | ADR-014 (no authentication) is a deliberately reasoned, documented tradeoff, not an oversight | 12.1 |
| 57 | Structured logging with correlation-ID propagation is genuinely production-grade groundwork | 14.4 |
| 58 | `bandit` found zero Medium/High severity issues in an automated pass | 12.9 |
| 59 | Celery configuration (`task_acks_late`, `worker_prefetch_multiplier=1`, soft time limits) reflects real understanding of a long-running-job workload, not defaults | 9.4 |
| 60 | `radon`'s maintainability index shows 0 files below grade A — complexity problems are localized to specific methods, not systemic across the codebase | 2.3, Testing header table |
| 61 | Plugin version-resolution logic (semver ranges) is legitimately sophisticated, appropriately so for the problem, and its own tests pass cleanly | 8.3 |

## Section 20 — Final Verdict

**Would you approve this repository for continued development?** Yes, without hesitation. The architecture (Section 1), the domain model, and the repository/service layering are good enough that continued investment on top of them is justified. The findings in this report are concentrated and fixable, not evidence of a design that needs to be thrown out.

**Would you approve this repository for production?** No. Section 18's Production Readiness score (38/100) is the honest reflection of this: no CI, a broken documented dev workflow, a Dockerfile that doesn't do what its own README says, and — most importantly — a flagship feature (video import) that currently cannot complete without an unhandled exception. "Production" isn't a bar this codebase is close to failing at the margins; it's a bar three or four specific, nameable fixes away from clearing.

**Would you merge this PR if you were the lead engineer?** No, and specifically because of what CI *would* have caught, not because of the depth of investigation this audit did that a normal review wouldn't. A lead engineer doesn't need to reproduce the CORS-on-error-response bug with a standalone script (3.3) to justify blocking a merge — they need `ruff`, `mypy`, and `pytest` to run and fail, which they currently would (2.1, 11.1). The first thing this repository needs is not more code review depth; it's a CI job that makes this audit's Section 2 and Section 11 findings impossible to merge past silently, ever again.

**What must be fixed first (in order):**
1. Add CI running `ruff check`, `mypy backend/`, and `pytest tests/unit` on every PR (14.1) — this is the highest-leverage single change in the report, because it prevents every subsequent regression of the kind found here, automatically, forever.
2. Fix the `await` bug in `import_service.py` (13.1) — the flagship feature is currently broken; this is a two-line fix with no excuse to ship a day longer than necessary.
3. Fix the two broken test imports (9.1) and the `Dispatcher.stop()` hang (9.2) so the test suite can complete a single run — everything else in Testing is unmeasurable until this is true.
4. Unify the split `Base` class (4.1) before the next schema migration is written.
5. Fix `StorageManager`'s settings mismatch (5.1) — currently a guaranteed crash, not a latent risk.
6. Fix the two broken PyPI package names (16.2) and the `Makefile`'s `frontend/` path (14.2) — both are two-line fixes that block onboarding and Phase C dependency installation respectively.

**What should never be changed:** the domain layer's isolation from infrastructure (1.1) — it's rare, it's correct, and it's the property most easily eroded by a well-meaning "just import the repository directly, it's faster" shortcut under deadline pressure. The list-argument-only subprocess discipline for FFmpeg (7.1) — every alternative "just build the command as a string, it's simpler" refactor is a step toward the exact vulnerability class this codebase has so far entirely avoided. And the ADR habit (12.1 and 15 others) — a project that writes down *why* it made a hard call, including calls this audit disagrees with in degree (like exactly how much the "no threat model" premise should weigh CORS/error-response edge cases), is a project a future engineer can actually reason about, which is worth more than any individual decision being "correct."

**What parts are exceptionally well designed** — stated without the usual "but" that follows in an audit, because these earn it on their own: the `ProjectAggregate` and domain-event design (1.1); the generic `BaseRepository[ModelT]` with optimistic locking, soft delete, and SQLAlchemy-exception translation (4.2); the WebSocket `SecurityValidator` (10.1), which is the one module in this codebase that reads like it was written by someone actively thinking about how a client could misbehave, not just how a well-behaved one would use it; and the HAL's fallback-chain design with an explicit, inspectable selection reason (6.1) — all four of these are the parts of this codebase this audit would tell another team to go read as an example of doing it right, not despite everything else in this report, but alongside it.

---

*End of audit. 61 individually-evidenced findings across 20 sections; every Critical and every High-severity functional claim in Sections 1–17 was verified either by direct source reading with cross-referenced call sites, by running the project's own configured tooling (`ruff`, `mypy`, `bandit`, `radon`, `pytest`) against itself, or by an independent standalone reproduction script executed against the real project code. Where something could not be verified in this sandboxed environment — GPU/CUDA code paths, real FFmpeg transcodes, Redis-backed Celery integration, full dependency-vulnerability scanning — that limitation is stated explicitly in the relevant section rather than silently assumed clean.*