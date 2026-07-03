# Sprint 4.6 A4 — Implementation Execution Plan

---

## 1. Executive Summary

### Implementation Goals
Introduce a centralized `FFmpegFilterEscaper` into the FFmpeg infrastructure layer and wire it into every code path that constructs FFmpeg filter graph strings (`-vf`, `-af`, `-filter_complex`). This prevents malformed filter arguments when Phase C introduces AI-generated text, user-sourced subtitle files, and dynamic filter expressions.

### Expected Result
- New file: `backend/infrastructure/ffmpeg/escape.py` — a pure-function module with 4 static methods
- Modified files: `command.py` (11 method bodies), `scene.py` (2 methods), `__init__.py` (exports)
- All 4 public API methods of `FFmpegFilterEscaper` fully tested
- Zero behavioral changes for existing code paths (all current filter values are numeric/safe)
- All existing tests pass unchanged

### Files Affected

| File | Type | LOC Changed |
|------|------|-------------|
| `backend/infrastructure/ffmpeg/escape.py` | **New** | ~90 |
| `backend/infrastructure/ffmpeg/command.py` | Modified | ~25 (add escaper calls) |
| `backend/infrastructure/ffmpeg/scene.py` | Modified | ~4 (add import + escaper calls) |
| `backend/infrastructure/ffmpeg/__init__.py` | Modified | ~2 (add export) |
| `tests/unit/ffmpeg/test_escape.py` | **New** | ~150 |

### Estimated Complexity
**Low** (2/10). Pure function additions with no new dependencies, no state, no architecture changes. The module has only stdlib imports (`re`, `pathlib`).

### Overall Risk
**Very Low**. All changes are additive. The escaper is idempotent (double-calling produces same result as single-calling). Existing code paths pass numeric-only values which have no special characters and pass through unchanged. Rollback is a single `git checkout`.

---

## 2. Exact Change Order

### Step 1 — Create escape.py and its test file (parallel-safe)

**Why this order is safest**: The new module has zero dependencies on the rest of the codebase. Creating it first establishes the API that all subsequent steps will use. The unit test file can be written simultaneously because test inputs are known in advance.

**Dependency satisfied**: Provides `FFmpegFilterEscaper` class that Step 3 and Step 4 will import.

**What breaks if order changes**: If Step 3 (CommandBuilder wiring) runs before Step 1, the import `from backend.infrastructure.ffmpeg.escape import FFmpegFilterEscaper` will raise `ModuleNotFoundError`. The codebase would be in a broken state until Step 1 completes.

### Step 2 — Wire escaper into CommandBuilder

**Why this order is safest**: CommandBuilder is the single choke point where all filter strings are built. Fixing it first ensures that all downstream consumers (AudioExtractor, ExportEncoder, FrameExtractor, ProxyGenerator, ThumbnailGenerator, FFmpegManager) automatically get escaped filter strings without any changes.

**Dependency satisfied**: Requires Step 1 (`FFmpegFilterEscaper` import).

**What breaks if order changes**: If Step 3 (scene.py) runs before Step 2, scene.py's filter strings would be escaped but CommandBuilder's would not — creating an inconsistency where some filter paths are safe and others are not. This is not a hard break (no crash), but it defeats the purpose of the sprint.

### Step 3 — Wire escaper into scene.py

**Why this order is safest**: scene.py builds commands directly (bypassing CommandBuilder). It is a secondary code path that handles scene detection, not general-purpose filtering. Wiring it last minimizes the surface area of changes.

**Dependency satisfied**: Requires Step 1 (`FFmpegFilterEscaper` import).

**What breaks if order changes**: Same as Step 2 — inconsistency between escaped and unescaped code paths.

### Step 4 — Export from __init__.py

**Why this order is safest**: Adding `FFmpegFilterEscaper` to `__init__.py`'s `__all__` makes it a first-class export of the `backend.infrastructure.ffmpeg` package. This should be last because it's purely cosmetic — the escaper is already usable via `backend.infrastructure.ffmpeg.escape.FFmpegFilterEscaper`.

**Dependency satisfied**: None (cosmetic change only).

**What breaks if order changes**: Nothing. The escaper works regardless of whether it's in `__all__`.

### Step 5 — Run full regression

**Why this is last**: The full test suite validates that no existing functionality was affected. It must run after all code changes are complete.

---

## 3. Atomic Commits

### Commit 1 — `Create escape.py`

```
Files:
  A  backend/infrastructure/ffmpeg/escape.py

Message:
  feat(ffmpeg): add FFmpegFilterEscaper with 4 static methods

  escape_filter_value()   — Escapes filtergraph special characters
  escape_filter_path()    — Escapes filesystem paths (Windows-safe)
  escape_drawtext_text()  — Double-escapes for drawtext expressions
  normalize_path_for_ffmpeg() — Normalizes backslashes to forward slashes

  All methods are idempotent. No project dependencies (stdlib only).
```

**Reversible**: `git rm backend/infrastructure/ffmpeg/escape.py`

### Commit 2 — `Add unit tests`

```
Files:
  A  tests/unit/ffmpeg/test_escape.py

Message:
  test(ffmpeg): add 25 unit tests for FFmpegFilterEscaper

  Covers: special characters, Windows paths, drawtext text,
  path normalization, Unicode, idempotency, empty string, edge cases.
```

**Reversible**: `git rm tests/unit/ffmpeg/test_escape.py`

### Commit 3 — `Wire CommandBuilder`

```
Files:
  M  backend/infrastructure/ffmpeg/command.py

Message:
  fix(ffmpeg): wire FFmpegFilterEscaper into all CommandBuilder filter methods

  All 11 methods that build -vf/-af/-filter_complex strings now pass
  their values through the escaper. Numeric-only values pass through
  unchanged (idempotent). Subtitle/caption paths are now correctly
  escaped for Windows compatibility.
```

**Reversible**: `git checkout HEAD~ -- backend/infrastructure/ffmpeg/command.py`

### Commit 4 — `Wire scene.py`

```
Files:
  M  backend/infrastructure/ffmpeg/scene.py

Message:
  fix(ffmpeg): wire FFmpegFilterEscaper into scene detection commands

  scene.py builds commands directly (bypassing CommandBuilder).
  Filter expressions and split commands now pass through the escaper.
```

**Reversible**: `git checkout HEAD~ -- backend/infrastructure/ffmpeg/scene.py`

### Commit 5 — `Export module`

```
Files:
  M  backend/infrastructure/ffmpeg/__init__.py

Message:
  feat(ffmpeg): export FFmpegFilterEscaper from package __init__

  Adds FFmpegFilterEscaper to the public API of
  backend.infrastructure.ffmpeg.
```

**Reversible**: `git checkout HEAD~ -- backend/infrastructure/ffmpeg/__init__.py`

### Commit 6 — `Regression verification`

```
Files:
  (none — verification only)

Message:
  chore(ffmpeg): regression verification for Sprint 4.6 A4

  Full test suite: 0 regressions.
  All 25+ new unit tests pass.
  All pre-existing tests pass.
```

**Reversible**: N/A (no file changes)

---

## 4. Verification After Every Commit

### Commit 1 — Create escape.py

| Check | Command | Expected Result |
|-------|---------|----------------|
| Import | `python -c "from backend.infrastructure.ffmpeg.escape import FFmpegFilterEscaper"` | Exit code 0, no output |
| Lint | `ruff check backend/infrastructure/ffmpeg/escape.py` | No warnings |
| Type check | `mypy backend/infrastructure/ffmpeg/escape.py` (if configured) | No errors |
| Code review | Manual inspection | All 4 methods implemented per spec |
| **Rollback point** | `git rm backend/infrastructure/ffmpeg/escape.py` | ✅ |

### Commit 2 — Add unit tests

| Check | Command | Expected Result |
|-------|---------|----------------|
| Run tests | `python -m pytest tests/unit/ffmpeg/test_escape.py -v --tb=long` | All 25+ tests pass |
| Import | `python -c "from tests.unit.ffmpeg.test_escape import *"` | Exit code 0 |
| **Rollback point** | `git rm tests/unit/ffmpeg/test_escape.py` | ✅ |

### Commit 3 — Wire CommandBuilder

| Check | Command | Expected Result |
|-------|---------|----------------|
| Import | `python -c "from backend.infrastructure.ffmpeg.command import CommandBuilder"` | Exit code 0 |
| Smoke test | `python -c "from backend.infrastructure.ffmpeg.command import CommandBuilder; c = CommandBuilder.probe('test.mp4'); print(c)"` | Valid command list |
| Escaping test | `python -c "from backend.infrastructure.ffmpeg.command import CommandBuilder; c = CommandBuilder.burn_subtitles('in.mp4', 'C:/path/sub.srt', 'out.mp4'); print(c)"` | Path is escaped in output |
| Lint | `ruff check backend/infrastructure/ffmpeg/command.py` | No warnings |
| **Rollback point** | `git checkout HEAD~ -- backend/infrastructure/ffmpeg/command.py` | ✅ |

### Commit 4 — Wire scene.py

| Check | Command | Expected Result |
|-------|---------|----------------|
| Import | `python -c "from backend.infrastructure.ffmpeg.scene import SceneExtractionHelper"` | Exit code 0 |
| Lint | `ruff check backend/infrastructure/ffmpeg/scene.py` | No warnings |
| **Rollback point** | `git checkout HEAD~ -- backend/infrastructure/ffmpeg/scene.py` | ✅ |

### Commit 5 — Export module

| Check | Command | Expected Result |
|-------|---------|----------------|
| Package import | `python -c "from backend.infrastructure.ffmpeg import FFmpegFilterEscaper"` | Exit code 0 |
| Lint | `ruff check backend/infrastructure/ffmpeg/__init__.py` | No warnings |
| **Rollback point** | `git checkout HEAD~ -- backend/infrastructure/ffmpeg/__init__.py` | ✅ |

### Commit 6 — Regression verification

| Check | Command | Expected Result |
|-------|---------|----------------|
| Full test suite | `python -m pytest tests/ -v --tb=line -q` | All tests pass (0 failures) |
| New tests | `python -m pytest tests/unit/ffmpeg/test_escape.py -v` | All 25+ tests pass |
| **Rollback point** | Full revert: `git checkout HEAD~5 -- backend/infrastructure/ffmpeg/` | ✅ |

---

## 5. Failure Recovery

### Step 1 — Create escape.py

| Possible Failure | Symptoms | Root Cause | Rollback | Forward Fix |
|-----------------|----------|------------|----------|-------------|
| **Syntax error** | Python `SyntaxError` on import | Typo or malformed code | `git rm file` then recreate | Fix syntax and re-run verification |
| **Logic error in escape_filter_value** | Test failure: input `":"` produces `":"` instead of `"\\:"` | Incorrect regex or replace logic | Fix the method and re-run tests | Add test for that specific case |
| **Escape incorrectly modifies safe values** | Test failure: input `"1920"` produces `"\\1920"` | Overly aggressive regex | Fix regex pattern | Use character-class pattern matching |
| **Idempotency failure** | `escape(escape(x)) != escape(x)` | Escaped chars re-scanned as literal | Fix to handle already-escaped sequences | Test explicitly with pre-escaped input |

### Step 2 — Wire CommandBuilder

| Possible Failure | Symptoms | Root Cause | Rollback | Forward Fix |
|-----------------|----------|------------|----------|-------------|
| **ImportError** | `ModuleNotFoundError: No module named 'backend.infrastructure.ffmpeg.escape'` | Step 1 not completed | Complete Step 1 first | N/A (dependency ordering) |
| **Wrong import path** | `AttributeError: module '...' has no attribute 'FFmpegFilterEscaper'` | Incorrect import statement | `git checkout HEAD~` the file | Fix import path |
| **Double escaping** | Path `"C:/path"` becomes `"C\\:/path"` (already escaped) then gets escaped again | Caller already escaped value | Fix to make idempotent | Ensure escaper detects already-escaped patterns |
| **Missed escape site** | A filter value in `thumbnail()` or `proxy()` not escaped | Human error during code review | Add the missed call | Code review checklist catches this |

### Step 3 — Wire scene.py

| Possible Failure | Symptoms | Root Cause | Rollback | Forward Fix |
|-----------------|----------|------------|----------|-------------|
| **ImportError** | Same as Step 2 | Same as Step 2 | Same as Step 2 | Same as Step 2 |
| **Filter expression broken** | FFmpeg scene detection fails | Escaping a control character that should remain literal | `git checkout HEAD~` the file | Use `escape_filter_value_soft()` for known-safe expressions |

### Step 4 — Export from __init__.py

| Possible Failure | Symptoms | Root Cause | Rollback | Forward Fix |
|-----------------|----------|------------|----------|-------------|
| **Missing import** | `ImportError` when accessing `FFmpegFilterEscaper` from package | Forgot `from .escape import FFmpegFilterEscaper` | Add the import line | Verify with `python -c "from backend.infrastructure.ffmpeg import FFmpegFilterEscaper"` |

---

## 6. Regression Matrix

| Module | Risk | Reason | Verification | Expected |
|--------|------|--------|-------------|----------|
| `FFmpegManager` | 🟢 None | Orchestrator only; delegates all filter building to CommandBuilder | Import + smoke test | Works unchanged |
| `CommandBuilder` | 🟢 Negligible | All filter values are currently numeric or hardcoded. Escaping is idempotent for these. | Compare output of 3 methods (e.g. `extract_frames`, `crop`, `proxy`) before/after for same inputs | Identical output |
| `burn_subtitles()` | 🟡 Low | Previously unescaped paths now escaped. Only affects paths with special characters (none exist in current code). | Unit test with known-safe path | Path unchanged |
| `render_captions()` | 🟡 Low | Same as `burn_subtitles()` | Unit test with known-safe path | Path unchanged |
| `build_filter_graph()` | 🟢 None | All values from `VideoFilters` are numeric or hardcoded | Unit test | Identical |
| `AudioExtractor` | 🟢 None | Delegates to CommandBuilder | Import + smoke test | Works unchanged |
| `ExportEncoder` | 🟢 None | Delegates to CommandBuilder | Import + smoke test | Works unchanged |
| `FrameExtractor` | 🟢 None | Delegates to CommandBuilder | Import + smoke test | Works unchanged |
| `ProxyGenerator` | 🟢 None | Delegates to CommandBuilder | Import + smoke test | Works unchanged |
| `ThumbnailGenerator` | 🟢 None | Delegates to CommandBuilder | Import + smoke test | Works unchanged |
| `SceneExtractionHelper` | 🟢 None | Sensitivity parameter is float (no special chars) | Import + smoke test | Works unchanged |
| `FFprobeService` | 🟢 None | No filter strings | Import | Works unchanged |
| `VideoInfoExtractor` | 🟢 None | No filter strings | Import | Works unchanged |
| `ProcessRunner` | 🟢 None | Receives pre-escaped commands; no changes needed | Import | Works unchanged |
| `backend/api/routes/videos.py` | 🟢 None | No filter strings in API routes | Import | Works unchanged |

### Edge Case Analysis

| Edge Case | Status | Verification |
|-----------|--------|-------------|
| Empty subtitle path | Passes through (empty string → empty string) | Unit test |
| Path with only safe chars (`/home/user/file.srt`) | Unchanged | Unit test |
| Path with spaces (`My Subtitle.srt`) | Space preserved | Unit test |
| Path with Unicode (`файл.srt`) | Unchanged (UTF-8 safe) | Unit test |
| Numeric scale values (`1920`, `1080`) | Unchanged | Unit test |
| Float fps values (`23.976`) | Unchanged | Unit test |
| Already-escaped input (`\\:`) | Idempotent — not double-escaped | Unit test |
| Empty filter string | Passes through | Unit test |

---

## 7. Coding Rules

These rules are mandatory. Violations must be caught during code review and fixed before merging.

### Rule 1 — No escaping outside FFmpegFilterEscaper

```
No other module may contain FFmpeg escaping logic.
All escaping must go through FFmpegFilterEscaper methods.
```

**Rationale**: Centralized escaping is the entire point of this sprint. Distributed escaping creates inconsistency.

### Rule 2 — No public API changes

```
No method signature, return type, or parameter name changes
to any existing class or function in the public API.
```

**Rationale**: The sprint goal is to add escaping, not to redesign APIs. API changes increase regression risk.

### Rule 3 — No new dependencies

```
escape.py may ONLY import:
  - re (stdlib)
  - pathlib.Path (stdlib)
No third-party packages. No internal project modules.
```

**Rationale**: The escaper must be usable everywhere in the FFmpeg layer without creating circular import risk.

### Rule 4 — No unrelated file modifications

```
Only the 5 files listed in Section 1 may be created or modified.
No other file in the repository may be touched.
```

**Rationale**: Scope creep is the most common cause of sprint delays.

### Rule 5 — No opportunistic refactoring

```
If you see code that could be improved (variable names, formatting,
dead code), ignore it. Do not change it.
```

**Rationale**: Every change carries risk. Refactoring belongs in a separate sprint.

### Rule 6 — Idempotency

```
All escape methods must be idempotent:
  escape(x) == escape(escape(x))
```

**Rationale**: Prevents double-escaping bugs when multiple call sites both escape the same value.

### Rule 7 — No behavior change for safe inputs

```
For any input string that contains NO special characters,
the output must equal the input.
```

**Rationale**: Prevents regressions in existing code paths.

---

## 8. Definition of Done

Implementation is complete ONLY when every item on this checklist passes.

### Code

- [ ] `backend/infrastructure/ffmpeg/escape.py` created with all 4 methods implemented
- [ ] `backend/infrastructure/ffmpeg/command.py` imports `FFmpegFilterEscaper` and uses it in all 11 filter-building methods
- [ ] `backend/infrastructure/ffmpeg/scene.py` imports `FFmpegFilterEscaper` and uses it in `detect_scenes()` and `split_command()`
- [ ] `backend/infrastructure/ffmpeg/__init__.py` exports `FFmpegFilterEscaper` in `__all__`

### Tests

- [ ] `tests/unit/ffmpeg/test_escape.py` created with ≥ 25 test cases
- [ ] `escape_filter_value` tests cover all 8 special characters
- [ ] `escape_filter_value` tests cover idempotency
- [ ] `escape_filter_value` tests cover Unicode/emoji
- [ ] `escape_filter_path` tests cover Linux, Windows, UNC paths
- [ ] `escape_drawtext_text` tests cover `%`, `{`, `}`, `:`, `\`, `'`
- [ ] `normalize_path_for_ffmpeg` tests cover backslash normalization
- [ ] All tests pass (`python -m pytest tests/unit/ffmpeg/test_escape.py -v`)

### Verification

- [ ] All new imports work (`python -c "from backend.infrastructure.ffmpeg import FFmpegFilterEscaper"`)
- [ ] No lint warnings on any modified file
- [ ] Full test suite passes (`python -m pytest tests/ -v --tb=line -q`)
- [ ] Zero regressions identified

### Security

- [ ] Windows paths with drive letters are correctly normalized
- [ ] Paths with colons are escaped
- [ ] No shell injection vector introduced (subprocess uses list args)

### Documentation

- [ ] Docstrings on all 4 public methods explaining escaping rules

---

## 9. Code Review Checklist

The reviewer MUST verify every item below before approving.

### Architecture

- [ ] Does the escaper live in the correct layer? (infrastructure/ffmpeg) ✅ / ❌
- [ ] Is there any escaping logic outside `FFmpegFilterEscaper`? ❌ (must be none)
- [ ] Are there any new public APIs beyond the 4 specified methods? ❌ (must be none)
- [ ] Has the architecture drifted from the approved design? ❌ (must be no)

### Correctness

- [ ] Is `escape_filter_value()` idempotent? Test: `escape(escape(x)) == escape(x)`
- [ ] Does `escape_filter_path()` handle Windows drive letters (`C:` → `C\:`)?
- [ ] Does `escape_filter_path()` handle UNC paths (`\\server\share` → `//server/share`)?
- [ ] Does `escape_drawtext_text()` escape `%` (drawtext expression prefix)?
- [ ] Does `escape_drawtext_text()` escape `{` `}` (metadata expansion markers)?
- [ ] Are numeric values (integers, floats) passed through unchanged?
- [ ] Is the empty string handled correctly?
- [ ] Are Unicode and emoji characters preserved?

### Integration

- [ ] Does `CommandBuilder.burn_subtitles()` pass subtitle_path through `escape_filter_path()`?
- [ ] Does `CommandBuilder.render_captions()` pass captions_path through `escape_filter_path()`?
- [ ] Does `CommandBuilder.export()` pass `params.video_filters` through escape?
- [ ] Does `CommandBuilder.build_filter_graph()` pass all filter values through escape?
- [ ] Does `CommandBuilder.thumbnail()` scale/pad values pass through escape?
- [ ] Does `CommandBuilder.proxy()` scale values pass through escape?
- [ ] Does `CommandBuilder.smart_scale()` all filter values pass through escape?
- [ ] Does `CommandBuilder.crop()` all crop params pass through escape?
- [ ] Do ALL 11 filter-building methods in CommandBuilder use the escaper?
- [ ] Does `scene.py` use the escaper?

### Safety

- [ ] No double-escaping possible? (idempotency verified)
- [ ] No new circular imports? (`escape.py` imports only `re` and `pathlib`)
- [ ] No modifications to `ProcessRunner`, `FFprobeService`, `VideoInfoExtractor`, or any filter module (audio.py, export.py, etc.)?
- [ ] No modification to API route files?
- [ ] No modification to test files other than the new `test_escape.py`?

### Standards

- [ ] Ruff/Flake8 passes on all modified files
- [ ] Mypy passes on all modified files (if configured in project)
- [ ] All docstrings follow project convention
- [ ] Type hints on all function signatures
- [ ] No `# type: ignore` comments added

---

## 10. Final Go / No-Go Decision

### ✅ GO — Ready for Implementation

**Justification**:

| Factor | Assessment |
|--------|-----------|
| **Complexity** | Low — pure function additions, no state, no architecture changes |
| **Risk** | Very low — idempotent, additive, fully revertible |
| **Dependencies** | None — stdlib only |
| **Testability** | High — pure functions with deterministic inputs/outputs |
| **Merge conflicts** | Unlikely — these files are not in active development |
| **Rollback safety** | Complete — single `git checkout` reverts everything |
| **Team readiness** | N/A — single-implementer sprint |

**Blockers identified**: None.

**Pre-implementation checklist**:
- [x] Design Review approved
- [x] Architecture Review approved
- [x] Implementation Specification approved
- [x] Implementation Execution Plan approved
- [x] All FFmpeg source files read and understood
- [x] All escape call sites identified (11 in command.py + 2 in scene.py)
- [x] All test scenarios enumerated (25+)
- [x] No open questions remaining

**Estimated wall-clock time**: ~2 hours for a senior engineer.

---

## Appendix A — Exact Escape Call Sites

### command.py (11 methods)

| Method | Line(s) | Filter String | What to Escape | Safe? |
|--------|---------|---------------|----------------|-------|
| `extract_frames()` | ~29 | `f"fps={p.fps}"` | `p.fps` (float) | ✅ Already safe |
| `thumbnail()` | ~49 | `f"scale={p.width}:{p.height}:..."` | `p.width`, `p.height` (int) | ✅ Already safe |
| `thumbnail()` | ~50 | `f"pad={p.width}:{p.height}:..."` | `p.width`, `p.height` (int) | ✅ Already safe |
| `proxy()` | ~71 | `f"scale={p.width}:{p.height}:..."` | `p.width`, `p.height` (int) | ✅ Already safe |
| `normalize_audio()` | ~118 | `f"loudnorm=I={loudness_target}:..."` | `loudness_target` (float) | ✅ Already safe |
| `waveform()` | ~133 | `f"showwavespic=s={width}x{height}:..."` | `width`, `height` (int) | ✅ Already safe |
| `smart_scale()` | ~145 | `f"scale={width}:{height}:..."` | `width`, `height` (int) | ✅ Already safe |
| `crop()` | ~160 | `f"crop={params.width}:{params.height}:{params.x}:{params.y}"` | All ints | ✅ Already safe |
| `convert_fps()` | ~172 | `f"fps={fps}"` | `fps` (float) | ✅ Already safe |
| `export()` | ~203 | `params.video_filters` (custom string) | User-supplied string | ⚠️ **Escape needed** |
| `export()` | ~206 | `f"scale={params.scale[0]}:{params.scale[1]}..."` | Scale values (int) | ✅ Already safe |
| `burn_subtitles()` | ~240 | `f"subtitles={subtitle_path}"` | File path | 🔴 **Escape needed** |
| `burn_subtitles()` | ~242 | `f":force_style='{burn_style}'"` | Style string | ⚠️ **Escape needed** |
| `render_captions()` | ~263 | `f"ass={captions_path}"` | File path | 🔴 **Escape needed** |
| `render_captions()` | ~272 | `f"subtitles={captions_path}"` | File path | 🔴 **Escape needed** |
| `build_filter_graph()` | ~283-300 | Multiple f-strings with scale/crop/pad/fps/rotate/custom | Various | ⚠️ **Escape needed for custom** |

**Implementation pattern**: For every `f"..."` string that includes a variable, wrap the variable in `FFmpegFilterEscaper.escape_filter_value()`. For paths, use `FFmpegFilterEscaper.escape_filter_path()`. For drawtext-specific values, use `FFmpegFilterEscaper.escape_drawtext_text()`.

**Example transformations**:
```python
# Before:
f"subtitles={subtitle_path}"
# After:
f"subtitles={FFmpegFilterEscaper.escape_filter_path(subtitle_path)}"

# Before:
f"scale={p.width}:{p.height}:force_original_aspect_ratio=decrease"
# After:
f"scale={FFmpegFilterEscaper.escape_filter_value(p.width)}:{FFmpegFilterEscaper.escape_filter_value(p.height)}:force_original_aspect_ratio=decrease"
```

### scene.py (2 methods)

| Method | Line(s) | Filter String | What to Escape | Safe? |
|--------|---------|---------------|----------------|-------|
| `detect_scenes()` | ~54 | `f"select='gt(scene,{sensitivity})',showinfo"` | `sensitivity` (float) | ✅ Already safe |
| `split_command()` | ~88 | `-ss`, `-t` values are floats; paths are from caller | Timestamps (float), output_path (path) | ✅ Already safe (paths use list args, not filter strings) |
