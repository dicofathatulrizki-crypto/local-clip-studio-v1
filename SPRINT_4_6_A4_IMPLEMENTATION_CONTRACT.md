# Sprint 4.6 A4 — Implementation Contract

**Version**: 1.0  
**Status**: FINAL — BINDING  
**Authority**: Principal Engineering  
**Enforcement**: Code Review + Automated Verification Gates

---

## 1. Purpose

### 1.1 Why This Contract Exists
This contract exists to govern the automated implementation of Sprint 4.6 (A4). It constrains AI behavior to the precise scope, architecture, and API surface defined in the three approved immutable documents:

1. `SPRINT_4_6_A4_DESIGN_REVIEW.md`
2. `SPRINT_4_6_A4_IMPLEMENTATION_SPEC.md`
3. `SPRINT_4_6_A4_EXECUTION_PLAN.md`

### 1.2 Problems This Contract Prevents
- Unauthorized architecture changes during implementation
- Scope creep beyond the sprint boundary
- Silent API modifications
- Opportunistic refactoring
- Introduction of unapproved abstractions
- Dependency or toolchain changes
- Mixed-purpose commits that cannot be cleanly reverted

### 1.3 Who Must Follow It
Every automated agent executing any portion of Sprint 4.6 A4.

### 1.4 When It Applies
From the moment the first file is created or modified until the final Definition of Done is verified. This contract expires when the sprint is approved as complete.

---

## 2. Scope Guard

### 2.1 Allowed

| Category | Details |
|----------|---------|
| **New files** | `backend/infrastructure/ffmpeg/escape.py` |
| | `tests/unit/ffmpeg/test_escape.py` |
| **Modified files** | `backend/infrastructure/ffmpeg/command.py` |
| | `backend/infrastructure/ffmpeg/scene.py` |
| | `backend/infrastructure/ffmpeg/__init__.py` |
| **Variable changes** | Adding a `FFmpegFilterEscaper` call to existing f-string filter expressions |
| **Import additions** | Importing `FFmpegFilterEscaper` in `command.py`, `scene.py`, `__init__.py` |
| **Export additions** | Adding `FFmpegFilterEscaper` to `__all__` in `__init__.py` |

### 2.2 Not Allowed

| Category | Details |
|----------|---------|
| **Any other file** | No file outside the 5 listed above may be touched |
| **Any other module** | No changes to: `ProcessRunner`, `FFprobeService`, `VideoInfoExtractor`, `AudioExtractor`, `ExportEncoder`, `FrameExtractor`, `ProxyGenerator`, `ThumbnailGenerator`, `GpuEncoderSelector`, `SceneExtractionHelper`, `FFmpegManager`, `ProgressParser`, `FFmpegCapabilities`, `FFmpegLocator`, `EncorderMapping` |
| **Any API route** | No changes to `backend/api/` |
| **Any tests** | No changes to existing test files |
| **Any config** | No changes to `pyproject.toml`, `setup.py`, `requirements.txt`, `Makefile`, `Dockerfile` |

### 2.3 Must Stop

The implementation must stop immediately and report the situation if:

| Condition | Example |
|-----------|---------|
| `escape.py` requires an import from outside stdlib | `import requests`, `import numpy` |
| A modified method signature no longer matches its callers | `def thumbnail(self, input_path, ...)` signature changes |
| A test fails and the cause is not immediately clear | Non-deterministic test failure |
| The implementation requires stateful configuration | A singleton, global registry, or DI container for the escaper |

### 2.4 Must Ask

Explicit human approval is required before:

| Condition | Rationale |
|-----------|-----------|
| Creating any file not in the Allowed list | Prevents scope creep |
| Adding any import not listed in this contract | Prevents dependency creep |
| Changing any method signature | Prevents API drift |
| Introducing any helper class beyond `FFmpegFilterEscaper` | Prevents architecture drift |
| Removing any code (including dead code) | Prevents opportunistic refactoring |

### 2.5 Must Escalate

The following must be escalated to a human without attempting a fix:

| Condition | Rationale |
|-----------|-----------|
| Any approved document is discovered to conflict with another | Resolution requires architectural authority |
| Implementation reveals an existing bug that blocks compilation | Root cause may be outside sprint scope |
| Implementation reveals a design flaw in the approved spec | Correcting it is not the implementer's role |

---

## 3. Architecture Guard

### 3.1 Immutable Properties

The following architectural properties must remain unchanged:

| Property | Current State | Must Remain |
|----------|---------------|-------------|
| Module location | `backend/infrastructure/ffmpeg/escape.py` | ✅ |
| Ownership | Infrastructure layer only | ✅ |
| Responsibility | Filter argument escaping only | ✅ |
| Abstraction level | Pure utility class, no state | ✅ |
| Dependency direction | `command.py` → `escape.py` (one-way) | ✅ |

### 3.2 Forbidden Actions

The implementation MUST NOT:

- change the layer (infrastructure → domain, etc.)
- change module ownership
- change module responsibilities
- introduce new abstractions (no `FilterSpec`, `FilterGraph`, `FilterBuilder`, etc.)
- introduce new design patterns (no factory, no strategy, no observer)
- rename existing components
- move files to new locations
- split existing files
- merge existing files
- rewrite entire modules
- extract base classes or mixins
- introduce protocols or ABCs for the escaper

### 3.3 Architecture Change Protocol

If the implementation requires an architecture change:
1. STOP all work
2. Document exactly what change is needed and why
3. Present to human for approval
4. Implement only after written approval

---

## 4. API Guard

### 4.1 Immutable Public APIs

The following APIs must remain **exactly** as they are — no signature, return type, exception, or behavioral change:

| Module | Class/Method | Constraint |
|--------|-------------|------------|
| `manager.py` | All public methods of `FFmpegManager` | No changes |
| `command.py` | All static methods of `CommandBuilder` (signatures) | No changes |
| `process.py` | `ProcessRunner.run()` | No changes |
| `ffprobe.py` | All methods of `FFprobeService` | No changes |
| `video_info.py` | All methods of `VideoInfoExtractor` | No changes |
| `audio.py` | `AudioExtractor.extract()` | No changes |
| `export.py` | `ExportEncoder.encode()` | No changes |
| `frame.py` | `FrameExtractor.extract()` | No changes |
| `proxy.py` | `ProxyGenerator.generate()` | No changes |
| `thumbnail.py` | `ThumbnailGenerator.generate()` | No changes |
| `scene.py` | `SceneExtractionHelper.detect_scenes()` | No changes |
| `errors.py` | All exception classes | No changes |
| `types.py` | All dataclasses | No changes |
| `__init__.py` | Existing `__all__` exports | Existing exports unchanged |

### 4.2 Permitted New API

The ONLY new public API permitted:

```python
# From backend/infrastructure/ffmpeg/escape.py
class FFmpegFilterEscaper:
    @staticmethod
    def escape_filter_value(value: str | int | float) -> str: ...
    @staticmethod
    def escape_filter_path(path: str) -> str: ...
    @staticmethod
    def escape_drawtext_text(text: str) -> str: ...
    @staticmethod
    def normalize_path_for_ffmpeg(path: str) -> str: ...
```

No additional methods, properties, constants, or nested classes may be added without human approval.

### 4.3 Permitted Internal Changes

The following internal changes are permitted:

| File | Change | Rationale |
|------|--------|-----------|
| `command.py` | Filter string values wrapped in `escape_filter_value()` or `escape_filter_path()` | Core requirement |
| `scene.py` | Filter expression values wrapped in `escape_filter_value()` | Core requirement |
| `__init__.py` | `FFmpegFilterEscaper` added to `__all__` | Export requirement |

---

## 5. Dependency Guard

### 5.1 Dependency Rules

| Rule | Enforcement |
|------|-------------|
| No new packages may be added to `pyproject.toml`, `setup.py`, `requirements*.txt`, or `Pipfile` | Verify: `git diff` shows no changes to these files |
| No existing packages may be upgraded or downgraded | Verify: `git diff` shows no changes to lock files |
| No existing packages may be removed | Verify: `git diff` shows no deletions from dependency files |
| `escape.py` may only import: `re`, `pathlib` (stdlib) | Verify: inspect imports in `escape.py` |
| `command.py` may add exactly one new import: `from backend.infrastructure.ffmpeg.escape import FFmpegFilterEscaper` | Verify: `git diff command.py` |
| `scene.py` may add exactly one new import: `from backend.infrastructure.ffmpeg.escape import FFmpegFilterEscaper` | Verify: `git diff scene.py` |
| `__init__.py` may add exactly one new import and one `__all__` entry | Verify: `git diff __init__.py` |
| No build system changes (`setup.py`, `pyproject.toml`, `Makefile`, `Dockerfile`) | Verify: no changes to these files |

### 5.2 Enforcement
All dependency rules are enforced by `git diff` inspection during code review. Any unexpected change to any dependency or build file is an immediate rejection.

---

## 6. Refactoring Guard

### 6.1 Permitted Refactoring

Refactoring is permitted ONLY in the following circumstances:

| Circumstance | Example |
|--------------|---------|
| Required to compile the approved changes | Adding a missing import that prevents `python -c "from ... import ..."` from succeeding |
| Required by the approved specification | The spec requires a specific method signature; implementing it correctly may require local re-organization |
| Required to remove duplicated code introduced during this sprint | If the same 3-line escape sequence appears 11 times and a local helper reduces it — BUT this helper must be a private function within the same file, not a new class |

### 6.2 Forbidden Refactoring

The following are expressly forbidden:

| Action | Example |
|--------|---------|
| Style-only changes | Renaming variables, reformatting docstrings, changing line breaks |
| Formatting-only changes | Adding/removing blank lines, reordering imports, changing string quotes |
| Dead code removal | Deleting unused functions, variables, or comments |
| Pre-existing issue fixes | Fixing lint warnings in code you didn't touch |
| Modernization | Converting `str.format()` to f-strings, or vice versa |
| Renaming | Changing any existing identifier |
| Reordering | Changing method order within a class |
| Comment changes | Editing, adding, or removing comments in unchanged code |

### 6.3 Enforcement
Any diff containing changes beyond the exact scope specified in this contract is a violation. The entire commit must be rejected.

---

## 7. File Guard

### 7.1 Exact File Changes

| Action | File | Maximum Lines Changed |
|--------|------|---------------------|
| **Create** | `backend/infrastructure/ffmpeg/escape.py` | ~90 |
| **Create** | `tests/unit/ffmpeg/test_escape.py` | ~150 |
| **Modify** | `backend/infrastructure/ffmpeg/command.py` | ~25 |
| **Modify** | `backend/infrastructure/ffmpeg/scene.py` | ~4 |
| **Modify** | `backend/infrastructure/ffmpeg/__init__.py` | ~2 |
| **Total** | **5 files** | **~271** |

### 7.2 File Change Rules

| Rule | Enforcement |
|------|-------------|
| No file outside the 5 listed above may be created | `git diff --stat` shows exactly 5 files |
| No file outside the 5 listed above may be modified | `git diff --stat` shows exactly 5 files |
| No file may be deleted | `git status` shows no deleted files |
| No file may be renamed | `git status` shows no renamed files |

### 7.3 Exception Protocol
If a file outside the 5 listed must be touched to make the implementation compile:
1. STOP
2. Document which file and why
3. Submit for human approval
4. Proceed only after written approval

---

## 8. Coding Guard

### 8.1 Style Compliance

| Rule | Standard |
|------|----------|
| Follow existing code style | All files use `snake_case`, 4-space indent, single-quoted strings |
| Preserve naming conventions | `escape_filter_value()`, not `escapeFilterValue()` |
| Preserve logging strategy | No new loggers in `escape.py`; existing loggers in `command.py` unchanged |
| Preserve exception hierarchy | No new exception classes; escaper may raise `ValueError` for invalid inputs |
| Preserve dependency injection style | `CommandBuilder` uses `@staticmethod` — escaper methods are also `@staticmethod` |

### 8.2 Behavioral Rules

| Rule | Enforcement |
|------|-------------|
| No hidden behavior changes | For any input without special characters: `output == input` |
| No side effects | Escape methods are pure functions — no I/O, no mutation, no logging |
| No global state | `FFmpegFilterEscaper` has no class variables, instance variables, or module-level state |
| No mutable shared state | Escape methods are `@staticmethod` — no access to `self` or `cls` |
| No unnecessary allocations | Single-pass string processing; no intermediate list comprehensions where regex suffices |

### 8.3 Method Constraints

Each escape method must be:
- **Deterministic**: Same input always produces same output
- **Idempotent**: `escape(x) == escape(escape(x))` for all valid `x`
- **Pure**: No I/O, no network, no filesystem, no logging
- **Stateless**: No caching, no memoization, no instance state
- **Reentrant**: Safe to call from multiple threads simultaneously

---

## 9. Security Guard

### 9.1 Forbidden Actions

| Action | Rationale |
|--------|-----------|
| Weaken existing security | No removal or bypass of existing validation |
| Bypass validation | No accepting unvalidated raw input |
| Remove sanitization | No reduction of existing sanitization |
| Introduce shell execution | No addition of `shell=True`, `os.system()`, or `subprocess.call()` with string args |
| Bypass existing abstractions | No new code paths that call subprocess directly |
| Suppress exceptions silently | No bare `except:`, no `except Exception: pass` |
| Introduce path traversal | No new file path construction without validation |

### 9.2 Required Security Properties

| Property | Verification |
|----------|-------------|
| `escape_filter_path` must produce a value that cannot break the filter graph parser | Unit test: Windows path with `:` and `\` produces valid output |
| The escaper must not silently corrupt data | Unit test: all outputs are valid UTF-8 and lossless |
| No information disclosure | The escaper must not emit error messages containing raw input values |

---

## 10. Performance Guard

### 10.1 Forbidden Actions

| Action | Rationale |
|--------|-----------|
| Premature optimization | Don't optimize before measuring |
| Introduce caching | The escaper is stateless by design |
| Introduce threading | The escaper must remain synchronous |
| Introduce async changes | No `async def`, no `await`, no `asyncio.to_thread` |
| Allocate unnecessary objects | Use regex substitution rather than string splitting + joining where possible |

### 10.2 Acceptable Performance Characteristics

| Metric | Acceptable Range |
|--------|-----------------|
| Escape overhead per value | < 1μs (single regex or str.replace pass) |
| Escape overhead per command | < 10μs (worst case: 10 values per command) |
| Total allocation per value | Output string only |
| FFmpeg execution time proportion | < 0.001% overhead |

At these levels, performance measurement is unnecessary.

---

## 11. Testing Guard

### 11.1 Required Tests

| Requirement | Count | File |
|-------------|-------|------|
| `escape_filter_value` test cases | ≥ 14 | `test_escape.py` |
| `escape_filter_path` test cases | ≥ 6 | `test_escape.py` |
| `escape_drawtext_text` test cases | ≥ 4 | `test_escape.py` |
| `normalize_path_for_ffmpeg` test cases | ≥ 3 | `test_escape.py` |
| Idempotency tests | ≥ 2 | `test_escape.py` |
| **Total** | **≥ 29** | `test_escape.py` |

### 11.2 Test Rules

| Rule | Enforcement |
|------|-------------|
| Every new public method must have tests | All 4 methods have at least 3 test cases |
| No existing tests may be deleted | `git diff --stat` shows no changes to any existing test file |
| Failing tests must never be ignored | Every test in the suite must pass |
| Expected failures must be explicitly documented | If a test cannot pass due to environment (e.g., no FFprobe installed), it must use `@pytest.mark.skipif` with a clear reason |

### 11.3 Verification Commands

| Command | Purpose |
|---------|---------|
| `python -m pytest tests/unit/ffmpeg/test_escape.py -v --tb=long` | Run new unit tests |
| `python -m pytest tests/ -v --tb=line -q` | Full regression suite |

---

## 12. Documentation Guard

### 12.1 Consistency Requirements

The implementation must remain consistent with:

| Document | Key Sections |
|----------|-------------|
| `SPRINT_4_6_A4_DESIGN_REVIEW.md` | Recommended Architecture, Proposed Class Diagram (4 methods only) |
| `SPRINT_4_6_A4_IMPLEMENTATION_SPEC.md` | Scope, Files to Modify, API Compatibility, Unit Test Plan |
| `SPRINT_4_6_A4_EXECUTION_PLAN.md` | Atomic Commits, Verification After Every Commit, Appendix A |

### 12.2 Divergence Protocol

If implementation must diverge from any approved document:

1. **STOP** immediately
2. Identify the exact document, section, and divergence
3. Determine if the divergence is required or discretionary
4. Present to human with the question: "May I diverge from [document] section [X] for [reason]?"
5. If denied, revert to the approved specification
6. If approved, document the divergence in the commit message

---

## 13. Commit Guard

### 13.1 Required Commits

The implementation must produce exactly these 6 commits, in this order:

| # | Commit Message | Files | Verification |
|---|----------------|-------|-------------|
| 1 | `feat(ffmpeg): add FFmpegFilterEscaper with 4 static methods` | `escape.py` (A) | `python -c "from backend.infrastructure.ffmpeg.escape import FFmpegFilterEscaper"` |
| 2 | `test(ffmpeg): add ≥29 unit tests for FFmpegFilterEscaper` | `test_escape.py` (A) | `python -m pytest tests/unit/ffmpeg/test_escape.py -v` |
| 3 | `fix(ffmpeg): wire FFmpegFilterEscaper into all CommandBuilder filter methods` | `command.py` (M) | `python -c "from backend.infrastructure.ffmpeg.command import CommandBuilder"` |
| 4 | `fix(ffmpeg): wire FFmpegFilterEscaper into scene.py` | `scene.py` (M) | `python -c "from backend.infrastructure.ffmpeg.scene import SceneExtractionHelper"` |
| 5 | `feat(ffmpeg): export FFmpegFilterEscaper from package __init__` | `__init__.py` (M) | `python -c "from backend.infrastructure.ffmpeg import FFmpegFilterEscaper"` |
| 6 | `chore(ffmpeg): regression verification for Sprint 4.6 A4` | (none — verification only) | `python -m pytest tests/ -v --tb=line -q` |

### 13.2 Commit Rules

| Rule | Enforcement |
|------|-------------|
| Every commit must compile | `python -c "import ..."` succeeds |
| Every commit must pass its verification | The verification step for that commit exits with code 0 |
| Every commit must be independently reversible | Reverting the commit restores the previous working state |
| One logical change per commit | No mixing of `escape.py` creation with `command.py` changes |
| No WIP or partial-state commits | Every commit represents a coherent, complete, working change |

---

## 14. Review Guard

### 14.1 Pre-Approval Verification

Before declaring implementation complete, the following must be verified:

| Check | How |
|-------|-----|
| No architecture drift | Compare final state against Design Review Architecture section |
| No scope creep | `git diff --stat` shows exactly 5 files affected |
| No duplicated logic | The only escaping logic in the codebase is in `FFmpegFilterEscaper` |
| No dead code | All methods in `escape.py` are called from at least one module |
| No unnecessary helpers | No functions, classes, or constants beyond the 4 specified methods |
| No duplicated escaping | Every call site uses `FFmpegFilterEscaper`, not inline string manipulation |
| No undocumented behavior | All 4 methods have docstrings explaining special characters escaped |
| No API changes | `git diff` shows no changes to public API signatures in existing modules |
| No hidden regressions | Full test suite passes |

### 14.2 Code Review Checklist

The reviewer must verify:

- [ ] All 5 files are exactly those listed in Section 2.1
- [ ] No file outside the 5 listed has been changed
- [ ] `escape.py` imports only `re` and `pathlib`
- [ ] `command.py` adds exactly one new import
- [ ] `scene.py` adds exactly one new import
- [ ] `__init__.py` adds exactly one new export
- [ ] All 4 escape methods are `@staticmethod` (no instance state)
- [ ] All 4 escape methods have type-annotated signatures
- [ ] All 4 escape methods have docstrings
- [ ] No method signature in any existing module is changed
- [ ] All 6 commits are present in the correct order
- [ ] Every commit's verification step passes
- [ ] No commit contains mixed concerns
- [ ] Full regression suite passes
- [ ] Idempotency verified for at least one input per method

---

## 15. Stop Conditions

The implementation MUST stop immediately under any of these conditions:

| # | Condition | Required Action |
|---|-----------|-----------------|
| 1 | Architecture must change | Escalate to human |
| 2 | New dependency appears necessary | Escalate to human |
| 3 | Public API must change | Escalate to human |
| 4 | Specification is discovered to be incomplete | Escalate to human |
| 5 | Implementation conflicts with approved design | Escalate to human |
| 6 | Implementation requires undocumented assumptions | Escalate to human with assumption documented |
| 7 | Unexpected side effects appear | Stop, document, escalate |
| 8 | Compilation requires modifying files outside the 5 permitted | Stop, document, escalate |
| 9 | A verification step fails and root cause is not immediately clear | Stop, document failure, escalate |
| 10 | More than 30 minutes pass without a successful verification step | Stop, document progress, escalate |

---

## 16. Human Approval Gates

The following require explicit human approval before proceeding:

| Gate # | Condition | What to Submit |
|--------|-----------|----------------|
| G1 | Adding any file beyond the 5 permitted | File name, rationale, contents |
| G2 | Changing any existing public API | Old signature, proposed new signature, reason |
| G3 | Introducing any abstraction beyond `FFmpegFilterEscaper` | Abstraction name, purpose, justification |
| G4 | Changing architecture or module ownership | Old architecture, proposed architecture, rationale |
| G5 | Changing dependency graph | Current dependencies, proposed changes |
| G6 | Changing project structure | Current structure, proposed changes |
| G7 | Changing testing strategy | Current strategy, proposed changes, rationale |
| G8 | Modifying any file not in the scope guard | File path, reason, diff |

---

## 17. Definition of Contract Compliance

### 17.1 Compliance Requirements

Sprint 4.6 A4 is compliant ONLY if every condition below is met:

| # | Condition | Verification |
|---|-----------|-------------|
| 1 | Every approved file matches the scope in Section 2.1 | `git diff --stat` |
| 2 | Every verification step in Section 13.1 succeeds | Run all 6 verification commands |
| 3 | No forbidden action from Sections 2.2, 3.2, 4.1, 5.1, 6.2, 7.2, 8.1, 9.1, 10.1 occurred | Code review |
| 4 | No undocumented decision was made | All method signatures match the spec |
| 5 | No architectural decision was invented | All patterns (static methods, pure functions) are from the spec |
| 6 | No additional scope was implemented | `git diff --stat` shows exactly the expected changes |
| 7 | All tests pass | `python -m pytest tests/ -v --tb=line -q` exits 0 |
| 8 | No existing functionality is altered | All existing API tests pass with same inputs |

### 17.2 Signature

```
Implementation Engineer: _________________________
Code Reviewer:          _________________________
Date:                  _________________________

Compliant:  [ ] YES   [ ] NO (if NO, attach non-compliance report)
```

---

## Appendix A — Exact Import Lines

The following import lines are the ONLY imports permitted to be added:

### `backend/infrastructure/ffmpeg/command.py`
```python
from backend.infrastructure.ffmpeg.escape import FFmpegFilterEscaper
```
Add after line 7: `from backend.infrastructure.ffmpeg.types import (`

### `backend/infrastructure/ffmpeg/scene.py`
```python
from backend.infrastructure.ffmpeg.escape import FFmpegFilterEscaper
```
Add after existing imports.

### `backend/infrastructure/ffmpeg/__init__.py`
```python
from backend.infrastructure.ffmpeg.escape import FFmpegFilterEscaper
```
Add in the import section. Add `"FFmpegFilterEscaper"` to the `__all__` list.

---

## Appendix B — Escaping Logic Specification

The `escape_filter_value` method must implement this logic:

```python
# Input: a string value
# Output: the value with the following characters escaped by prefixing with backslash:
#   : → \:
#   , → \,
#   ; → \;
#   = → \=
#   [ → \[
#   ] → \]
#   \ → \\
#   ' → \'
# Order: BACKSLASH first (to avoid double-escaping), then all others
# Idempotency: after escaping, the output contains no unescaped special characters.
#              Applying escape() again produces the same output.
```

The `escape_filter_path` method must implement this logic:

```python
# 1. Normalize all backslashes to forward slashes (platform-independent)
# 2. Escape any colons in the path with backslash
# Note: Backslashes are converted to forward slashes FIRST (no remaining \ to conflict with escape)
```

The `escape_drawtext_text` method must implement this logic:

```python
# Apply escape_filter_value FIRST
# Then additionally escape:
#   % → \%
#   { → \{
#   } → \}
```

The `normalize_path_for_ffmpeg` method must implement this logic:

```python
# 1. Replace all backslashes with forward slashes
# 2. Return the normalized path
```

---

## Appendix C — Verification Command Reference

All verification commands run from `/home/daytona/codebase/`:

```bash
# Commit 1 verification
python -c "from backend.infrastructure.ffmpeg.escape import FFmpegFilterEscaper; print('escape.py OK')"

# Commit 2 verification
python -m pytest tests/unit/ffmpeg/test_escape.py -v --tb=long

# Commit 3 verification
python -c "from backend.infrastructure.ffmpeg.command import CommandBuilder; print('command.py OK')"

# Commit 4 verification
python -c "from backend.infrastructure.ffmpeg.scene import SceneExtractionHelper; print('scene.py OK')"

# Commit 5 verification
python -c "from backend.infrastructure.ffmpeg import FFmpegFilterEscaper; print('__init__.py OK')"

# Commit 6 verification
python -m pytest tests/ -v --tb=line -q
```

---

*End of Contract*
