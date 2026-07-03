# Sprint 4.6 — A4 Implementation Specification

## 1. Scope

### Inside Sprint 4.6

| Item | Description |
|------|-------------|
| `FFmpegFilterEscaper` class | New module at `backend/infrastructure/ffmpeg/escape.py` |
| `escape_filter_value()` | Core escape method for filter argument values |
| `escape_filter_path()` | Path-specific escape with Windows handling |
| `escape_drawtext_text()` | Double-escaped text for drawtext filter |
| `normalize_path_for_ffmpeg()` | Path normalization (backslash → forward slash) |
| Wiring into `CommandBuilder` | All 11 `CommandBuilder` methods that build filter strings call the escaper |
| Wiring into `scene.py` | Both `detect_scenes()` and `split_command()` call the escaper |
| `__init__.py` export | Export `FFmpegFilterEscaper` from the ffmpeg package |
| Unit test file | `tests/unit/ffmpeg/test_escape.py` |
| Integration test updates | Update existing tests to validate escaped output |

### Outside Sprint 4.6

| Item | Reason |
|------|--------|
| `FilterSpec` / `FilterGraph` dataclasses | Approved design review included these but the constraint says "Do NOT introduce FilterSpec yet unless absolutely required by the approved architecture." The escaper works as a function-level utility — structured dataclasses can be added later |
| Phase C feature implementation | AI captions, subtitle burn-in, auto zoom are future phases |
| Refactoring individual filter modules | AudioExtractor, ExportEncoder, FrameExtractor, etc. — they already delegate to CommandBuilder and need no changes |
| `video_filters` passthrough in `ExportParams` | This is a caller-supplied string that should be escaped by the caller. Documentation update is sufficient |
| Non-FFmpeg escaping | SQL, shell, filesystem path traversal are out of scope |
| Windows CI/CD setup | The escaper handles Windows paths correctly; testing on actual Windows is deferred |
| `ProcessRunner` changes | The runner receives pre-built command lists; escaping happens before it runs |
| FFprobe paths | FFprobe arguments don't use filter graph syntax — no escaping needed |

---

## 2. Files to Modify

### 2.1 — `backend/infrastructure/ffmpeg/command.py`

| Field | Value |
|-------|-------|
| **Reason** | This is where ALL filter strings are constructed. All 11 methods that build `-vf`, `-af`, or `-filter_complex` strings must pass values through the escaper. |
| **Functions affected** | `extract_frames()`, `thumbnail()`, `proxy()`, `normalize_audio()`, `waveform()`, `smart_scale()`, `crop()`, `convert_fps()`, `export()`, `burn_subtitles()`, `render_captions()`, `build_filter_graph()` |
| **Estimated LOC changed** | ~25 lines (add escaper calls at the point where filter strings are constructed) |
| **Breaking risk** | 🟢 None. All existing callers pass numeric-only values. Escaping numeric values is idempotent (no special chars → no change). The only behavioral change is that paths in `burn_subtitles()` and `render_captions()` are now correctly escaped. |
| **Change pattern** | `f"subtitles={subtitle_path}"` → `f"subtitles={FFmpegFilterEscaper.escape_filter_path(subtitle_path)}"` |

### 2.2 — `backend/infrastructure/ffmpeg/__init__.py`

| Field | Value |
|-------|-------|
| **Reason** | Export `FFmpegFilterEscaper` so it's part of the public `backend.infrastructure.ffmpeg` API |
| **Functions affected** | Add to `__all__` list |
| **Estimated LOC changed** | +2 lines |
| **Breaking risk** | 🟢 None. Adding a new export is non-breaking. |

### 2.3 — `backend/infrastructure/ffmpeg/scene.py`

| Field | Value |
|-------|-------|
| **Reason** | `detect_scenes()` and `split_command()` build FFmpeg command lists directly, bypassing `CommandBuilder`. They need escaping. |
| **Functions affected** | `detect_scenes()` — the filter expression `f"select='gt(scene,{sensitivity})',showinfo"` is currently safe (numeric sensitivity), but importing the escaper establishes the pattern. `split_command()` — paths embedded in commands. |
| **Estimated LOC changed** | ~4 lines (add import and wrap sensitivity value) |
| **Breaking risk** | 🟢 None. Numeric sensitivity has no special characters. |

---

## 3. New Files

### 3.1 — `backend/infrastructure/ffmpeg/escape.py`

| Field | Value |
|-------|-------|
| **Purpose** | Single source of truth for FFmpeg filter argument escaping |
| **Rationale** | Belongs in `backend.infrastructure.ffmpeg` because it is a cross-cutting concern for ALL FFmpeg filter building. No domain or application layer code needs this — only the FFmpeg command builder. |
| **Exported symbols** | `FFmpegFilterEscaper` (class), or equivalently top-level functions `escape_filter_value()`, `escape_filter_path()`, `escape_drawtext_text()`, `normalize_path_for_ffmpeg()` |
| **Dependencies** | `re` (stdlib), `pathlib.Path` (stdlib). No project dependencies. |
| **Public API** | See Section 5.2 |

### 3.2 — `tests/unit/ffmpeg/test_escape.py`

| Field | Value |
|-------|-------|
| **Purpose** | Comprehensive unit test suite for the escaper |
| **Rationale** | No existing tests exist for FFmpeg. This establishes the test pattern. |
| **Test count** | ~25 test cases (see Section 7) |

---

## 4. Dependency Graph

```
backend.infrastructure.ffmpeg.escape
    └── (stdlib only: re, pathlib)

backend.infrastructure.ffmpeg.command
    ├── backend.infrastructure.ffmpeg.escape  (NEW)
    └── backend.infrastructure.ffmpeg.types

backend.infrastructure.ffmpeg.scene
    ├── backend.infrastructure.ffmpeg.escape  (NEW)
    └── backend.infrastructure.ffmpeg.process

backend.infrastructure.ffmpeg.__init__
    ├── backend.infrastructure.ffmpeg.escape  (NEW)
    ├── backend.infrastructure.ffmpeg.command
    ├── backend.infrastructure.ffmpeg.scene
    └── (all other ffmpeg modules)
```

**No circular imports.** `escape.py` imports only stdlib. `command.py` imports `escape.py` — no reverse dependency exists.

---

## 5. API Compatibility

### 5.1 — Public APIs That Remain Identical

| API | Status |
|-----|--------|
| `FFmpegManager` — all public methods | ✅ Identical. Manager delegates to command builder + filter modules internally. |
| `CommandBuilder.probe()` | ✅ Identical. No filter strings. |
| `CommandBuilder.extract_audio()` | ✅ Identical. No filter strings (uses `-acodec`, `-ar`, `-ac`). |
| `CommandBuilder.concat()` | ✅ Identical. No filter strings. |
| `CommandBuilder.trim()` | ✅ Identical. No filter strings (uses `-ss`, `-t`). |
| `ProcessRunner.run()` | ✅ Identical. Receives pre-escaped commands. |
| `VideoInfoExtractor` — all methods | ✅ Identical. FFprobe only. |
| `FFprobeService` — all methods | ✅ Identical. FFprobe only. |
| `AudioExtractor` — all methods | ✅ Identical. Delegates to CommandBuilder. |
| `ExportEncoder` — all methods | ✅ Identical. Delegates to CommandBuilder. |
| `FrameExtractor` — all methods | ✅ Identical. Delegates to CommandBuilder. |
| `ProxyGenerator` — all methods | ✅ Identical. Delegates to CommandBuilder. |
| `ThumbnailGenerator` — all methods | ✅ Identical. Delegates to CommandBuilder. |
| `SceneExtractionHelper` — all methods | ✅ Identical. Internal escaping added. |
| `ExportParams`, `CropParams`, etc. | ✅ Identical. No schema changes. |

### 5.2 — New Public API

```python
class FFmpegFilterEscaper:
    """Centralized FFmpeg filter argument escaping."""

    @staticmethod
    def escape_filter_value(value: str | int | float) -> str:
        """Escape a value for use in -vf/-af/-filter_complex strings.
        Escapes: : , ; = [ ] \\ ' and space.
        Idempotent: calling twice on the same value produces same result.
        """

    @staticmethod
    def escape_filter_path(path: str) -> str:
        """Escape a filesystem path for use in filter arguments.
        Normalizes backslashes to forward slashes, escapes colons.
        Platforms: Linux, macOS, Windows.
        """

    @staticmethod
    def escape_drawtext_text(text: str) -> str:
        """Escape text for drawtext:text= parameter.
        Double-escapes for filtergraph + drawtext expression parser.
        Escapes: % { } : \\ ' in addition to filtergraph special chars.
        """

    @staticmethod
    def normalize_path_for_ffmpeg(path: str) -> str:
        """Normalize a path for FFmpeg: replace \\ with /, handle spaces."""
```

### 5.3 — Internal API Changes

| API | Change |
|-----|--------|
| `CommandBuilder.burn_subtitles()` | Internal: `subtitle_path` now passes through `escape_filter_path()` |
| `CommandBuilder.render_captions()` | Internal: `captions_path` now passes through `escape_filter_path()` |
| `CommandBuilder.export()` | Internal: `params.video_filters` now passes through escape. Scale values (numeric) unchanged. |
| `CommandBuilder.build_filter_graph()` | Internal: All filter parameter values pass through `escape_filter_value()` |
| `CommandBuilder.thumbnail()` | Internal: `vf_parts` values pass through escape |
| `CommandBuilder.proxy()` | Internal: Scale values pass through escape |
| `CommandBuilder.smart_scale()` | Internal: Scale/pad values pass through escape |
| `CommandBuilder.crop()` | Internal: Width/height/x/y pass through escape |
| All other CommandBuilder filter methods | Internal: Values pass through escape |

### 5.4 — Deprecations

**None.** No existing API is removed or deprecated.

---

## 6. Migration Order

### Step 1 — Create `escape.py` + unit tests

```
Actions:
  - Create backend/infrastructure/ffmpeg/escape.py
  - Create tests/unit/ffmpeg/test_escape.py
  - Implement all 4 static methods
  - Write all test cases (Section 7)
Verification:
  - python -m pytest tests/unit/ffmpeg/test_escape.py -v --tb=long
Expected: All 25+ tests pass
```

↓

### Step 2 — Wire escaper into `CommandBuilder`

```
Actions:
  - Add import to command.py
  - Update all 11 filter-building methods
  - Verify idempotency (numbers pass through unchanged)
Verification:
  - python -c "from backend.infrastructure.ffmpeg.command import CommandBuilder; print('Import OK')"
  - python -m pytest tests/unit/ffmpeg/ -v (existing tests)
Expected: Import works, existing tests pass
```

↓

### Step 3 — Wire escaper into `scene.py`

```
Actions:
  - Add import to scene.py
  - Update detect_scenes() and split_command()
Verification:
  - python -c "from backend.infrastructure.ffmpeg.scene import SceneExtractionHelper; print('Import OK')"
Expected: Import works, no runtime errors
```

↓

### Step 4 — Update `__init__.py` exports

```
Actions:
  - Add FFmpegFilterEscaper to __all__
Verification:
  - python -c "from backend.infrastructure.ffmpeg import FFmpegFilterEscaper; print('Export OK')"
Expected: Export works
```

↓

### Step 5 — Full regression

```
Actions:
  - Run all existing tests
  - Run integration tests
Verification:
  - python -m pytest tests/ -v --tb=line -q
Expected: No regressions (only pre-existing failures)
```

---

## 7. Unit Test Plan

### Test file: `tests/unit/ffmpeg/test_escape.py`

### Test Scenarios

#### `escape_filter_value()` — ~12 tests

| # | Input | Expected Output | Rationale |
|---|-------|----------------|-----------|
| 1 | `"simple"` | `"simple"` | No special characters |
| 2 | `"1920"` | `"1920"` | Numeric string, no escaping needed |
| 3 | `"path:value"` | `"path\\:value"` | Colon must be escaped |
| 4 | `"a,b,c"` | `"a\\,b\\,c"` | Commas must be escaped |
| 5 | `"a;b;c"` | `"a\\;b\\;c"` | Semicolons must be escaped |
| 6 | `"a=b"` | `"a\\=b"` | Equals must be escaped |
| 7 | `"[label]"` | `"\\[label\\]"` | Brackets must be escaped |
| 8 | `"back\\slash"` | `"back\\\\slash"` | Backslash must be escaped |
| 9 | `"it's"` | `"it\\'s"` | Single quote must be escaped |
| 10 | `"hello world"` | `"hello world"` | Spaces are allowed (FFmpeg parses within filter value) |
| 11 | `"a:b,c;d=e[f]g\\h'i"` | `"a\\:b\\,c\\;d\\=e\\[f\\]g\\\\h\\'i"` | All special characters combined |
| 12 | `""` | `""` | Empty string |
| 13 | `"  "` | `"  "` | Whitespace preserved (caller's responsibility to strip) |
| 14 | `"😀emoji"` | `"😀emoji"` | Unicode/emoji pass through unchanged (UTF-8 safe) |

#### `escape_filter_path()` — ~6 tests

| # | Input | Expected Output | Rationale |
|---|-------|----------------|-----------|
| 1 | `"/home/user/video.mp4"` | `"/home/user/video.mp4"` | Linux path, no escaping needed |
| 2 | `"/home/user/my video.mp4"` | `"/home/user/my video.mp4"` | Spaces allowed in paths within quotes |
| 3 | `"C:\\Users\\name\\video.mp4"` | `"C:/Users/name/video.mp4"` | Windows → forward slashes |
| 4 | `"C:\\path\\to\\subs.srt"` | `"C:/path/to/subs.srt"` | Windows drive colon → forward slash, backslashes normalized |
| 5 | `"\\\\server\\share\\video.mp4"` | `"//server/share/video.mp4"` | UNC path → forward slashes |
| 6 | `"/home/user/file:name.mp4"` | `"/home/user/file\\:name.mp4"` | Colon in filename (rare) must be escaped |

#### `escape_drawtext_text()` — ~4 tests

| # | Input | Expected Output | Rationale |
|---|-------|----------------|-----------|
| 1 | `"Hello World"` | `"Hello World"` | Plain text, no escaping |
| 2 | `"50% complete"` | `"50\\% complete"` | Percent must be escaped for drawtext |
| 3 | `"Time: 1:30"` | `"Time\\: 1\\:30"` | Colons double-escaped (filtergraph + drawtext) |
| 4 | `"Use {name}"` | `"Use \\{name\\}"` | Braces must be escaped for drawtext |

#### `normalize_path_for_ffmpeg()` — ~3 tests

| # | Input | Expected Output | Rationale |
|---|-------|----------------|-----------|
| 1 | `"C:\\Users\\name"` | `"C:/Users/name"` | Windows backslashes → forward slashes |
| 2 | `"/unix/path"` | `"/unix/path"` | Unix paths unchanged |
| 3 | `"mixed\\path/here"` | `"mixed/path/here"` | Mixed separators normalized |

#### Idempotency — ~2 tests

| # | Input | Verification | Rationale |
|---|-------|-------------|-----------|
| 1 | `"a:b"` | `escape(escape("a:b")) == escape("a:b")` | Double-escaping produces same result |
| 2 | `"/home/user"` | `escape(escape("/home/user")) == escape("/home/user")` | Path double-escaping idempotent |

---

## 8. Regression Plan

### Which Existing Tests Must Pass

| Test Suite | Expected Count | Notes |
|------------|---------------|-------|
| All existing unit tests | Pre-existing count | The escaper is additive; existing tests should pass unchanged |
| FFmpeg module import tests | 6 imports: `escape.py`, `command.py`, `scene.py`, `__init__.py`, `manager.py`, `import_service.py` | All modules import correctly |

### Which Integration Tests Must Be Rerun

No integration tests currently exist (`tests/` directory is empty). After implementation, running the full test suite is trivial:

```
python -m pytest tests/ -v --tb=line -q
```

**Expected result**: 0 failures (all tests pass).

### Regression Risk By Module

| Module | Risk | Justification |
|--------|------|---------------|
| `command.py` | 🟢 None | All existing callers pass numeric values. Escaping is idempotent for non-special chars. |
| `scene.py` | 🟢 None | Sensitivity is float (0.0-1.0), no special chars. |
| `audio.py` | 🟢 None | Delegates to CommandBuilder, no direct filter building. |
| `export.py` | 🟢 None | Delegates to CommandBuilder. |
| `frame.py` | 🟢 None | Delegates to CommandBuilder. |
| `proxy.py` | 🟢 None | Delegates to CommandBuilder. |
| `thumbnail.py` | 🟢 None | Delegates to CommandBuilder. |
| `manager.py` | 🟢 None | Orchestrator, no direct filter building. |

---

## 9. Risk Analysis

### Potential Regressions

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Double-escaping if caller already escaped | Low | Idempotency: `escape_value()` checks if the value already contains escaped sequences and avoids re-escaping |
| Backward compatibility with known-safe values | None | Numeric and simple string values pass through unchanged |
| Import error from new module | None | Module has no project dependencies, only stdlib |

### Performance Impact

| Metric | Impact |
|--------|--------|
| Escape overhead per filter value | < 1μs per value (single regex replacement) |
| Number of values escaped per command | Typically 2-10 (scale params, paths, filter names) |
| Total overhead per FFmpeg command | < 10μs — negligible compared to FFmpeg's execution time (seconds to minutes) |
| Memory | Zero additional allocations beyond the escaped string |

### Cross-Platform Issues

#### Windows

| Issue | Risk | Handling |
|-------|------|----------|
| `\` as path separator | High | `normalize_path_for_ffmpeg()` replaces `\` with `/` |
| `C:\` drive letter colon | High | Colon is escaped with `\:` for the filtergraph parser |
| UNC paths `\\server\share` | Medium | Converted to `//server/share` |
| Paths with spaces | Low | Spaces preserved; caller wraps in quotes |

#### Linux

| Issue | Risk | Handling |
|-------|------|----------|
| Path separator `/` | None | Not a special character in filtergraph syntax |
| Spaces in paths | Low | Spaces are valid in filter values |
| Unicode in paths | None | Pass through unchanged |

#### macOS

| Issue | Risk | Handling |
|-------|------|----------|
| Same as Linux | None | No additional issues |

---

## 10. Acceptance Criteria

All criteria are binary (pass/fail), measurable, and objective:

| # | Criterion | Verification Method |
|---|-----------|-------------------|
| 1 | `FFmpegFilterEscaper` module imports without error | `python -c "from backend.infrastructure.ffmpeg.escape import FFmpegFilterEscaper"` exits 0 |
| 2 | `escape_filter_value()` escapes all 8 special characters (`:`, `,`, `;`, `=`, `[`, `]`, `\`, `'`) | Unit test: output contains `\:` for input containing `:` |
| 3 | `escape_filter_value()` does not modify alphanumeric values | Unit test: `"1920"` → `"1920"` |
| 4 | `escape_filter_value()` is idempotent | Unit test: `escape(escape(x)) == escape(x)` for all test inputs |
| 5 | `escape_filter_path()` normalizes Windows backslashes | Unit test: `"C:\\path"` → `"C:/path"` |
| 6 | `escape_filter_path()` escapes drive colons | Unit test: `"C:\"` contains `\:` |
| 7 | `escape_filter_path()` handles UNC paths | Unit test: `"\\\\server\\share"` → `"//server/share"` |
| 8 | `escape_drawtext_text()` escapes `%`, `{`, `}` | Unit test: `"50% {name}"` → `"50\\% \\{name\\}"` |
| 9 | `normalize_path_for_ffmpeg()` replaces all backslashes | Unit test: input with mixed `/` and `\` produces only `/` |
| 10 | `CommandBuilder` imports after adding escaper | `python -c "from backend.infrastructure.ffmpeg.command import CommandBuilder"` exits 0 |
| 11 | `CommandBuilder.burn_subtitles()` escapes subtitle path | Unit test: command list contains escaped path |
| 12 | `CommandBuilder.render_captions()` escapes captions path | Unit test: command list contains escaped path |
| 13 | `SceneExtractionHelper` imports after adding escaper | `python -c "from backend.infrastructure.ffmpeg.scene import SceneExtractionHelper"` exits 0 |
| 14 | `FFmpegFilterEscaper` exported from `backend.infrastructure.ffmpeg` | `python -c "from backend.infrastructure.ffmpeg import FFmpegFilterEscaper"` exits 0 |
| 15 | All 25+ unit tests pass | `python -m pytest tests/unit/ffmpeg/test_escape.py -v` — all tests pass, 0 failures |
| 16 | Zero existing tests broken | Full test suite run — no regressions |
| 17 | Non-ASCII/Unicode values pass through unchanged | Unit test: emoji and CJK characters not modified |

---

## 11. Rollback Plan

### If Implementation Fails During Step 1 (escape.py creation)

```
git checkout -- backend/infrastructure/ffmpeg/escape.py
rm tests/unit/ffmpeg/test_escape.py  (if created)
```

**Impact**: None. No other files reference this module yet.

### If Implementation Fails During Step 2 (CommandBuilder wiring)

```
git checkout -- backend/infrastructure/ffmpeg/command.py
git checkout -- backend/infrastructure/ffmpeg/escape.py
```

**Impact**: None. No other files reference the escaper. All existing functionality restored.

### If Implementation Fails During Step 3 (scene.py wiring)

```
git checkout -- backend/infrastructure/ffmpeg/scene.py
```

**Impact**: None. The escaper remains available for future use but scene.py reverts to no-escaping state (same behavior as before).

### If Implementation Fails During Step 4 (__init__.py)

```
git checkout -- backend/infrastructure/ffmpeg/__init__.py
```

**Impact**: `FFmpegFilterEscaper` no longer exported from the package level, but still importable from `backend.infrastructure.ffmpeg.escape`.

### Complete Rollback

```bash
git checkout -- backend/infrastructure/ffmpeg/
rm -f tests/unit/ffmpeg/test_escape.py
```

Reverts all FFmpeg infrastructure files to pre-Sprint-4.6 state. Zero residual changes.

---

## 12. Simplification Notes (Design Review → Implementation)

The approved design review proposed `FilterSpec` and `FilterGraph` dataclasses. These are **deferred** for the following technical justification:

1. **Not required for escaping**: The escaper is a pure function library. It takes a string value and returns an escaped string. No struct/container needed.

2. **Would increase scope 3×**: Introducing `FilterSpec` would require refactoring all 11 CommandBuilder methods from returning `list[str]` to building structured filter specs, then converting back to strings. This delays the core escaping fix.

3. **Can be added later**: When Phase C introduces AI-generated filter graphs, `FilterSpec` can be introduced as a new API on top of the existing escaper. The escaper's API (`escape_filter_value()`, etc.) remains the same either way.

4. **Makes migration testable incrementally**: Adding escaping to existing methods is a line-by-line change (replace `f"scale={w}:{h}"` with `f"scale={escape(w)}:{escape(h)}"`). Introducing `FilterSpec` would require rewriting entire methods.

**Decision**: Implement `FFmpegFilterEscaper` as a utility class with static methods. Do NOT introduce `FilterSpec`/`FilterGraph`. The existing `CommandBuilder` method signatures remain unchanged.

---

## 13. Final Engineering Recommendation

**READY FOR IMPLEMENTATION**

### Justification

1. **Clear scope**: One new file (`escape.py`), one new test file, modifications to three existing files (`command.py`, `scene.py`, `__init__.py`). ~30 lines of production code, ~150 lines of test code.

2. **No breaking changes**: All public APIs remain identical. All existing behavior for known-safe values is preserved.

3. **Idempotent**: Double-escaping produces the same result as single-escaping, ensuring safety regardless of call site.

4. **Testable**: The escaper is a pure function with no dependencies (stdlib only). ~25 test cases cover all special characters, paths, Unicode, and edge cases.

5. **Low risk rollback**: Each step is independently revertible. The complete rollback is `git checkout` of a single directory.

6. **Phase C ready**: Once wired, every filter value automatically gets correct escaping. AI caption text, subtitle paths, and auto-zoom expressions will be safe without any additional work.

7. **Cross-platform correct**: Windows paths (the hardest case) are handled via `\` → `/` normalization and colon escaping.

### Effort Estimate

| Phase | Effort | Dependencies |
|-------|--------|-------------|
| Step 1: escape.py + tests | ~1 hour | None |
| Step 2: CommandBuilder wiring | ~30 min | Step 1 |
| Step 3: scene.py wiring | ~10 min | Step 1 |
| Step 4: __init__.py + regression | ~10 min | Steps 1-3 |
| **Total** | **~2 hours** | — |
