# Sprint 4.6 — A4 Design Review: FFmpeg Filter Argument Escaping

## 1. Executive Summary

**Problem**: The FFmpeg infrastructure layer constructs filter graph strings (`-vf`, `-af`, `-filter_complex`) by concatenating user-generated content, filesystem paths, and AI-generated text directly into filter argument strings with **no centralized escaping strategy**. Every filter module (drawtext, subtitles, ass, scene detection, overlay, crop, scale, concat) builds its own argument strings independently. When Phase C introduces AI-generated caption text, subtitle files, and automated filter graphs, malformed or unescaped arguments will cause FFmpeg to misinterpret filter syntax — producing corrupted output, silent failures, or process crashes.

**Current state**: Zero escaping exists. Filter arguments are naive `f-string` or `+` concatenation. The project currently works because all inputs are controlled (hardcoded paths, known-safe filenames). Phase C's AI-generated content (text with colons, emoji, Unicode, filenames with spaces/punctuation) will break every filter.

**Recommendation**: Introduce a single `FFmpegFilterEscaper` utility class owned by the infrastructure layer, used by `FFmpegCommandBuilder` as the sole authority for filter argument escaping. No individual filter module should escape its own arguments.

**Estimated implementation effort**: ~2 days.

---

## 2. Current Architecture

The FFmpeg infrastructure layer follows this structure:

```
FFmpegManager          — Public async API, orchestrates all FFmpeg operations
├── FFprobeService     — Sync FFprobe metadata extraction (subprocess.run)
├── VideoInfoExtractor — Sync video property computation (calls FFprobeService)
├── ProcessRunner      — Async subprocess execution (asyncio.create_subprocess_exec)
├── FFmpegCommandBuilder — Builds command-line argument lists
└── Individual Filter Modules:
    ├── audio.py       — Audio extraction (ffmpeg -vn -acodec ...)
    ├── export.py      — Video encoding (ffmpeg -c:v libx264 ...)
    ├── frame.py       — Frame extraction (ffmpeg -vf fps=1/10 ...)
    ├── proxy.py       — Proxy generation (ffmpeg -vf scale=...)
    ├── scene.py       — Scene detection (ffmpeg -vf filter_complex)
    ├── thumbnail.py   — Thumbnail extraction (ffmpeg -vf ...)
    └── command.py     — Generic command construction
```

Each module constructs its own argument string and passes it to `ProcessRunner.run()` which receives the command as a **list of arguments** (`subprocess` takes a list, not a shell string — this is good and already prevents shell injection).

The problem is **within individual argument values** — filter graph strings that contain special characters like `:`, `,`, `[`, `]`, `\`, `'`, `%`, spaces, and Unicode.

---

## 3. Inventory of Filter Construction Sites

### 3.1 — command.py (FFmpegCommandBuilder)

| Function | Filter Type | Current Escaping | Risk Level |
|----------|------------|-----------------|------------|
| `build_command()` | Generic args list | None (uses list, safe from shell injection) | 🟢 Low |
| `_build_filter_args()` | Any `-vf`/`-af` | None — naive string join | 🔴 Critical |
| `_build_complex_filter()` | `-filter_complex` | None — naive string join | 🔴 Critical |

### 3.2 — audio.py (Audio Extraction)

| Function | Filter Type | Current Escaping | Risk Level |
|----------|------------|-----------------|------------|
| `extract_audio()` | `-vn -acodec` | None (uses list args, no filter strings) | 🟢 Low |
| `extract_audio_segment()` | `-ss -to -acodec` | None (timestamps safe) | 🟢 Low |
| `extract_waveform()` | `-filter_complex "compand"` | None — hardcoded filter, safe | 🟡 Medium |

### 3.3 — export.py (Encoding/Export)

| Function | Filter Type | Current Escaping | Risk Level |
|----------|------------|-----------------|------------|
| `encode()` | `-c:v libx264 -preset` | None (no filter strings) | 🟢 Low |
| `encode_with_filter()` | `-vf` arbitrary filter | None — caller-supplied filter string | 🔴 Critical |
| `encode_for_export()` | `-vf` + encoding params | None — may embed paths | 🟡 Medium |

### 3.4 — frame.py (Frame Extraction)

| Function | Filter Type | Current Escaping | Risk Level |
|----------|------------|-----------------|------------|
| `extract_frames()` | `-vf fps=1/10` | None — hardcoded fps, safe | 🟢 Low |
| `extract_frame_at_time()` | `-ss -vframes 1` | None — timestamp safe | 🟢 Low |
| `extract_frames_filter()` | `-vf select=eq(pict_type\,I)` | Backslash for comma — manual, inconsistent | 🟡 Medium |

### 3.5 — proxy.py (Proxy Generation)

| Function | Filter Type | Current Escaping | Risk Level |
|----------|------------|-----------------|------------|
| `generate_proxy()` | `-vf scale=...` | None — hardcoded scale params | 🟢 Low |
| `generate_thumbnail_proxy()` | `-vf scale=...:flags=...` | None — colon-separated params in f-string | 🟡 Medium |

### 3.6 — scene.py (Scene Detection)

| Function | Filter Type | Current Escaping | Risk Level |
|----------|------------|-----------------|------------|
| `detect_scenes()` | `-filter_complex "scenedetect"` | None — hardcoded filter name | 🟢 Low |
| `detect_scenes_threshold()` | `-filter_complex "scenedetect=threshold=..."` | None — numeric threshold safe | 🟢 Low |
| `extract_scene_metadata()` | `-filter_complex` with `metadata` | None — output parsing only | 🟢 Low |

### 3.7 — thumbnail.py

| Function | Filter Type | Current Escaping | Risk Level |
|----------|------------|-----------------|------------|
| `extract_thumbnail()` | `-vf select=eq(n\,X)` | Manual backslash for comma | 🟡 Medium |
| `extract_thumbnails_multi()` | `-vf fps=1/60` | None — hardcoded fps | 🟢 Low |

### 3.8 — manager.py (FFmpegManager)

| Function | Filter Type | Current Escaping | Risk Level |
|----------|------------|-----------------|------------|
| `probe()` | FFprobe args | None — safe (no filter strings) | 🟢 Low |
| `get_video_info()` | FFprobe args | None — safe | 🟢 Low |
| `extract_audio()` | Delegates to audio.py | Inherits risk | 🟡 Medium |
| `export_video()` | Delegates to export.py | Inherits risk | 🟡 Medium |
| `generate_proxy()` | Delegates to proxy.py | Inherits risk | 🟡 Medium |

### 3.9 — import_service.py (Import Service)

| Function | Filter Type | Current Escaping | Risk Level |
|----------|------------|-----------------|------------|
| `import_file()` | Path construction only | None — filename already UUID | 🟢 Low |
| `validate_file()` | FFprobe probe | None — safe | 🟢 Low |

### 3.10 — Future Phase C Sites (Not Yet Implemented)

| Feature | Filter Type | Planned Risk |
|---------|------------|-------------|
| AI Captions (drawtext) | `drawtext=text='...':fontfile=...` | 🔴 Critical |
| Subtitle burn-in | `subtitles=file.srt` | 🔴 Critical |
| ASS subtitle rendering | `ass=filename.ass` | 🔴 Critical |
| Smart crop | `crop=w:h:x:y` | 🟡 Medium |
| Auto zoom | `zoompan=z='...':d=...` | 🔴 Critical |
| Overlay graphics | `overlay=x:y` | 🟡 Medium |
| filter_complex AI graphs | Complex chained filters | 🔴 Critical |

### 3.11 — Search for Existing Escape/Sanitize Functions

**Result: NONE FOUND.** The codebase has no existing escaping or sanitization functions for FFmpeg filter arguments. There is no `escape_filter_arg`, `sanitize_path`, or similar utility anywhere in the FFmpeg layer.

---

## 4. Official FFmpeg Escaping Rules

### 4.1 — FFmpeg-utils Quoting and Escaping

The FFmpeg documentation defines a generic escaping mechanism:

| Rule | Description |
|------|-------------|
| **Single quotes `'...'`** | All characters inside are literal. No escaping inside quotes except `'` itself. |
| **Backslash `\`** | Escapes the next character. `\:` produces literal `:`. `\\` produces literal `\`. `\'` produces literal `'`. |
| **Unquoted whitespace** | Leading/trailing whitespace is stripped. Use quotes or backslash to preserve. |
| **Single quote inside single quotes** | NOT possible. Must use `'\\''` pattern: close quote, escaped quote, reopen quote. Example: `'It'\\''s'` → `It's`. |

### 4.2 — Filtergraph Syntax Special Characters

Within `-vf`, `-af`, and `-filter_complex` strings:

| Character | Meaning | Must Escape When Used Literally In Value |
|-----------|---------|----------------------------------------|
| `,` | Separates filters in a chain | ✅ Yes (`\,`) |
| `;` | Separates filter chains | ✅ Yes (`\;`) |
| `:` | Separates filter parameters | ✅ Yes (`\:`) |
| `=` | Separates parameter name from value | ✅ Yes (`\=`) |
| `[` | Opens a pad label | ✅ Yes (`\[`) |
| `]` | Closes a pad label | ✅ Yes (`\]`) |
| `'` | Quoting | ⚠️ See above |
| `\` | Escape character | ✅ Yes (`\\`) |

### 4.3 — Filter-Specific Escaping

#### drawtext
The `drawtext` filter has its own internal expression evaluator. Additional escaping requirements:

| Character | Meaning in drawtext | Must Escape |
|-----------|-------------------|-------------|
| `%` | Metadata expansion prefix (`%{pts}`, `%{localtime}`) | ✅ Yes (`\%`) |
| `:` | Expression separator | ✅ Yes (`\:`) |
| `'` | Has special meaning in expressions | ✅ Yes (`\'`) |
| `\` | Escape in expressions | ✅ Yes (`\\`) |
| `{` `}` | Metadata expansion markers | ✅ Yes (`\{` `\}`) |

**Multiple layers**: When `drawtext:text=` contains a colon, the filter graph parser sees it first (separator), then the drawtext expression parser sees it. This requires **double escaping**: `\\:` (once for filtergraph, once for drawtext). Through a shell: `\\\\:`.

**Recommendation**: Use `textfile=` instead of `text=` for any user-generated or AI-generated text content. This bypasses all escaping layers.

#### subtitles / ass
The `subtitles` and `ass` filters accept a file path. Special considerations:

| Character | Issue | Solution |
|-----------|-------|----------|
| `:` in Windows paths (C:\\) | Filter parser sees `:` as parameter separator | Escape as `C\\:` or use forward slashes |
| Spaces in paths | Path parsing breaks | Wrap path in single quotes or escape spaces |
| Unicode/emoji in path | FFmpeg supports UTF-8 paths natively | Use raw bytes, no special escaping needed |
| `file:` prefix | Explicit file syntax | `subtitles=file\\='/path/to/sub.srt'` |

### 4.4 — Summary: Characters That Must Be Escaped

| Character | Filtergraph | drawtext:text | drawtext:textfile | subtitles/ass path |
|-----------|-------------|---------------|-------------------|-------------------|
| `:` | ✅ `\:` | ✅ `\\:` | N/A | ✅ `\:` |
| `,` | ✅ `\,` | ✅ `\\,` | N/A | ✅ `\,` |
| `;` | ✅ `\;` | ✅ `\\;` | N/A | N/A |
| `=` | ✅ `\=` | ✅ `\\=` | N/A | N/A |
| `[` | ✅ `\[` | ✅ `\\[` | N/A | N/A |
| `]` | ✅ `\]` | ✅ `\\]` | N/A | N/A |
| `\` | ✅ `\\` | ✅ `\\\\` | N/A | ✅ `\\` |
| `'` | Use `'\\''` pattern | ✅ `\\'` | N/A | Mix with shell quoting |
| `%` | N/A | ✅ `\%` | N/A | N/A |
| `{` `}` | N/A | ✅ `\{` `\}` | N/A | N/A |
| Space | ✅ `\ ` or `'...'` | ✅ `\\ ` | N/A | ✅ `'path'` or forward slashes |
| Newline/Tab | ✅ Escape | ✅ Escape | N/A | N/A |
| UTF-8/Emoji | Safe (UTF-8) | Safe if font supports | Safe | Safe (UTF-8 paths) |

---

## 5. Cross-Platform Analysis

### 5.1 — Linux

| Factor | Analysis |
|--------|----------|
| **Path separator** | `/` — no conflict with filter syntax |
| **Shell** | Bash — uses `"..."` for argument grouping, `'...'` for literal strings |
| **Python subprocess** | `subprocess.run([...], shell=False)` — list-based exec, no shell involved |
| **Risk** | Low. Only filter syntax characters need escaping. |

### 5.2 — Windows

| Factor | Analysis |
|--------|----------|
| **Path separator** | `\` — conflicts with FFmpeg's escape character `\` |
| **Drive letters** | `C:\` — colon conflicts with filter parameter separator |
| **Shell** | cmd.exe or PowerShell — different quoting rules than bash |
| **Python subprocess** | `subprocess.run([...], shell=False)` — safe from shell injection, but `\` still conflicts in filter strings |
| **Risk** | High. Every path passed to a filter must have `\` → `\\` or `/` replacement, and `:` → `\:` |

### 5.3 — macOS

| Factor | Analysis |
|--------|----------|
| **Path separator** | `/` — same as Linux, no conflict |
| **HFS+ / APFS** | Case-insensitive by default — no impact on escaping |
| **Shell** | zsh (default) — similar to bash, `'...'` works for literals |
| **Risk** | Low. Same as Linux. |

### 5.4 — Platform Summary

The critical cross-platform issue is **Windows path handling**. All filter-relevant paths must be normalized:
- Replace `\` with `\\` (escape for filtergraph parser) or `/` (preferred)
- Escape `:` in drive letters with `\:`

---

## 6. Risk Assessment

### 6.1 — Command Injection

**Risk: 🟢 Low**

The codebase uses `subprocess.run([...], shell=False)` and `asyncio.create_subprocess_exec(...)` with argument lists, not shell strings. This eliminates shell injection as a vector. Filter arguments are passed as individual list elements, not concatenated into a shell command.

### 6.2 — Malformed Filter Graphs

**Risk: 🔴 Critical**

If unescaped special characters appear in filter arguments (spaces, colons, commas), FFmpeg will misinterpret the filter graph:
- A colon in a path becomes a parameter separator → wrong parameter values
- A comma in text becomes a filter chain separator → entire filter graph restructure
- A bracket in text becomes a pad label → FFmpeg tries to connect nonexistent pads

This causes silent corruption, wrong output, or FFmpeg crashes.

### 6.3 — Path Traversal

**Risk: ✅ Mitigated (by A3)**

The A3 fix (UUID filenames) eliminates user-supplied filenames from filesystem paths. However, `subtitles` and `ass` filters still accept file paths that could embed user-derived content.

### 6.4 — Shell Escaping Confusion

**Risk: 🟡 Medium**

Python's `subprocess` with argument lists prevents shell interpretation, but developers unfamiliar with this may add unnecessary shell-style escaping that creates double-escape situations.

### 6.5 — Windows-Specific Failures

**Risk: 🔴 Critical**

Backslashes in Windows paths are interpreted as escape characters by the filtergraph parser. A path like `C:\Users\name\subs.srt` will corrupt the filter string. Drive letter colons (`C:`) also conflict with filter parameter syntax.

### 6.6 — Linux-Specific Failures

**Risk: 🟡 Medium**

Less critical than Windows, but paths with spaces, parentheses, or Unicode characters can still break filter parsing.

---

## 7. Recommended Architecture

### 7.1 — Centralized Escaping: FFmpegFilterEscaper

**Decision: YES — introduce a dedicated `FFmpegFilterEscaper` class.**

Rationale:
1. **Single source of truth**: All escaping rules defined once, tested once, used everywhere.
2. **Consistent behavior**: No module can introduce its own incomplete or incorrect escaping.
3. **Audit trail**: One class to review for correctness instead of 10+ call sites.
4. **Phase C readiness**: New AI features (captions, subtitles) get correct escaping automatically.
5. **Testability**: One unit test suite for escaping instead of integration tests in every module.

### 7.2 — Architecture Diagram

```
                    FFmpegManager
                         │
                         ▼
               FFmpegCommandBuilder
                  │              │
                  ▼              ▼
          FFmpegFilterEscaper    ProcessRunner
                  │              (async subprocess)
                  ▼
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
audio.py    export.py     scene.py
frame.py    proxy.py     thumbnail.py
    │             │             │
    └─────────────┼─────────────┘
                  ▼
         No individual escaping
```

### 7.3 — Where Escaping Occurs

**Escaping happens inside `FFmpegCommandBuilder._build_filter_args()` and `_build_complex_filter()`, NOT inside individual filter modules.**

Each filter module constructs its arguments as **structured data** (not formatted strings):
```python
# Current (broken):
filter_string = f"scale={width}:{height}"

# Future (safe):
filter_args = {"scale": {"width": width, "height": height}}
# FFmpegCommandBuilder handles escaping internally
```

The call chain:
1. Filter module builds a `FilterSpec` (typed dataclass or dict)
2. `FFmpegCommandBuilder.build()` receives the `FilterSpec`
3. Builder calls `FFmpegFilterEscaper.escape_value()` for each parameter value
4. Builder joins the escaped values into the filtergraph string
5. Builder appends the filtergraph string as a single `-vf`/`-af` list element

---

## 8. Proposed Class Diagram

```python
class FFmpegFilterEscaper:
    """Centralized FFmpeg filter argument escaper."""

    # Filtergraph-level special characters
    FILTERGRAPH_SPECIAL = frozenset({':', ',', ';', '=', '[', ']', '\\', "'", ' '})

    # drawtext-specific special characters (additional to filtergraph)
    DRAWTEXT_SPECIAL = frozenset({'%', '{', '}', ':', '\\', "'"})

    @staticmethod
    def escape_filter_value(value: str) -> str
        """Escape a value for use in -vf/-af/-filter_complex strings.
        Use for generic filter parameter values.
        """

    @staticmethod
    def escape_drawtext_text(text: str) -> str
        """Escape text for drawtext:text= parameter.
        Double-escapes for filtergraph + drawtext expression parser.
        Preferred: use textfile= instead.
        """

    @staticmethod
    def escape_filter_path(path: str) -> str
        """Escape a filesystem path for use in filter arguments.
        Handles Windows backslash-to-escape conversion and drive colons.
        """

    @staticmethod
    def escape_filter_path_windows(path: str) -> str
        """Windows-specific: escape backslashes and drive colons."""

    @staticmethod
    def escape_filter_value_soft(value: str) -> str
        """Soft escape: only escape characters that would break parsing.
        Less aggressive, for known-safe values like timestamps.
        """

    @staticmethod
    def normalize_path_for_ffmpeg(path: str) -> str
        """Normalize a path for FFmpeg: replace backslashes, handle spaces."""


class FilterSpec:
    """Structured representation of a single filter with its parameters."""
    name: str
    params: dict[str, str | int | float | bool]


class FilterGraph:
    """Structured representation of a complete filter graph."""
    filters: list[FilterSpec]
    inputs: list[str]    # pad labels
    outputs: list[str]   # pad labels
```

---

## 9. Proposed Responsibilities

### FFmpegFilterEscaper Responsibilities

| Responsibility | Description |
|---------------|-------------|
| **Escape filter values** | Escape `:`, `,`, `;`, `=`, `[`, `]`, `\`, `'` in any filter argument value |
| **Escape drawtext text** | Double-escape for the drawtext expression parser's additional special characters |
| **Escape file paths** | Handle Windows backslash normalization and drive colon escaping |
| **Validate filenames** | Ensure subtitle/ASS file paths don't contain filter-breaking characters |
| **Normalize paths** | Convert Windows `\` to `/` (preferred) or `\\` |
| **Provide safe defaults** | Soft-escaping for known-safe numeric/boolean values to avoid unnecessary escape noise |

### Non-Responsibilities

- NOT responsible for shell escaping (subprocess uses list args)
- NOT responsible for encoding/format conversion
- NOT responsible for charset/Unicode normalization
- NOT responsible for SQL injection or other non-FFmpeg security

### Ownership

- **Owned by**: `backend/infrastructure/ffmpeg/escape.py`
- **Package**: Part of `backend.infrastructure.ffmpeg`
- **Imported by**: `FFmpegCommandBuilder` only (indirectly used by all filter modules)

---

## 10. Implementation Strategy

### Phase 1: Create FFmpegFilterEscaper (~0.5 day)

1. Create `backend/infrastructure/ffmpeg/escape.py`
2. Implement `escape_filter_value()` — the core method
3. Implement `escape_filter_path()` with Windows awareness
4. Implement `escape_drawtext_text()` with double-escaping
5. Implement `normalize_path_for_ffmpeg()`
6. Write comprehensive unit tests covering all special characters, edge cases, and cross-platform scenarios
7. Test against known problematic inputs: Windows paths, Unicode, emoji, colons, commas, brackets

### Phase 2: Integrate into FFmpegCommandBuilder (~0.5 day)

1. Modify `FFmpegCommandBuilder._build_filter_args()` to use `FFmpegFilterEscaper`
2. Modify `FFmpegCommandBuilder._build_complex_filter()` to use `FFmpegFilterEscaper`
3. Ensure all filter argument values pass through the escaper
4. Add integration tests verifying filter strings are correctly escaped

### Phase 3: Update Filter Modules (~0.5 day)

1. Convert each filter module from building raw strings to building structured `FilterSpec` objects
2. Remove any inline escaping that exists (e.g., manual `\,` in frame.py)
3. Verify no module bypasses the escaper

### Phase 4: Add FilterSpec/FilterGraph Dataclasses (~0.5 day)

1. Create typed dataclasses for structured filter construction
2. Add validation to ensure filter names and parameter names are safe
3. Add helper methods for common filter patterns

---

## 11. Migration Plan

### Step 1 — Create + Test Escaper (no integration)
```
Create escape.py with full test suite
Run: python -m pytest tests/unit/ffmpeg/test_escaper.py
```

### Step 2 — Integrate into Builder + Smoke Test
```
Wire escaper into FFmpegCommandBuilder
Run: python -m pytest tests/unit/ffmpeg/test_command_builder.py
```

### Step 3 — Module-by-Module Migration
```
For each module (audio, export, frame, proxy, scene, thumbnail):
  1. Convert to FilterSpec format
  2. Run module-specific tests
  3. Run integration tests
```

### Step 4 — Phase C Preparation
```
1. Document FFmpegFilterEscaper API
2. Add Phase C filter templates using the escaper
3. Add AI caption text escaping guide
```

---

## 12. Backward Compatibility

- **No API changes**: `FFmpegManager` public API unchanged
- **No behavior changes for safe inputs**: Only inputs with special characters will produce different (correct) output
- **No test breakage**: Existing tests should continue to pass because they use known-safe inputs
- **The normalization should be idempotent**: Calling `escape_filter_value()` twice should not double-escape

---

## 13. Edge Cases

| Edge Case | Risk | Handling |
|-----------|------|----------|
| Empty string value | 🟢 Safe | Pass through unchanged |
| Unicode text (CJK, Arabic) | 🟡 Medium | UTF-8 safe in modern FFmpeg; ensure no byte corruption |
| Emoji characters | 🟡 Medium | Should be escaped for filtergraph; font must support |
| Very long text (AI captions) | 🟡 Medium | Use `textfile=` for long text to avoid command-line limits |
| Newlines in text | 🔴 Critical | Must be escaped or removed; use `textfile=` |
| Tab characters | 🟡 Medium | Escape or use `textfile=` |
| Percent-encoded strings | 🟡 Medium | `%` must be `\%` in drawtext, but only `%` itself |
| Mixed single/double quotes | 🔴 Critical | Use FFmpeg's `'\\''` pattern or use `textfile=` |
| Windows UNC paths (`\\server\share`) | 🔴 Critical | Normalize to `/server/share` |
| Already-escaped strings | 🟡 Medium | Idempotency check: don't double-escape |
| AI-generated text with FFmpeg syntax | 🔴 Critical | Full escaping is non-negotiable for AI content |
| Empty caption text | 🟢 Safe | Skip filter entirely |
| Paths with trailing spaces | 🟡 Medium | Strip trailing whitespace or escape |
| Case sensitivity in extensions | 🟢 Safe | Case doesn't matter in filter parsing |
| Null bytes in input | 🔴 Critical | Reject immediately — safety hazard |

---

## 14. Open Questions

1. **Should `textfile=` be mandatory for AI caption text?** — Using `textfile=` bypasses all escaping layers and is the safest approach. Consider enforcing this in code review.

2. **How to handle filter modules that bypass the builder?** — Some modules call `ProcessRunner.run()` directly. Should they be refactored to go through `FFmpegCommandBuilder`, or should they use the escaper directly?

3. **What about the `-map` and stream specifiers?** — Stream specifiers use `:`, `#`, and other special characters. Should the escaper cover these too?

4. **Should we normalize paths globally in the escaper, or should each caller normalize first?** — Normalization inside the escaper is safer (no caller can forget), but it might produce unexpected results for intentionally non-standard paths.

5. **Should numeric/boolean parameter values skip escaping?** — Values like `width=1920`, `height=1080`, `enabled=1` don't need escaping. Soft-escaping (only escape if special chars present) adds complexity but reduces noise.

6. **How to handle the `subtitles` filter's `file:` and `original_size:` prefixes?** — These prefixes have their own syntax and must be recognized before escaping.

---

## 15. Final Recommendation

### ✅ Implement `FFmpegFilterEscaper` as a centralized utility class.

**Rationale**:

1. **Zero escaping exists today** — every filter argument is a naive concatenation, vulnerable to Phase C's AI-generated content.

2. **Centralized approach is the only viable architecture** — distributed escaping would create inconsistent behavior, skipped escapes, and duplicated logic that rapidly diverges.

3. **Phase C requires it** — AI captions (drawtext with AI-generated text), subtitle burn-in (subtitles/ass with user-sourced files), and auto zoom (zoompan with expression strings) all inject user-or-AI-generated content into filter strings. Without centralized escaping, these features will produce corrupted or failed FFmpeg commands.

4. **The effort is proportional** — ~2 days for complete implementation, with clear phases and safe rollout.

5. **Cross-platform correctness** — Windows paths are the hardest problem, and a centralized escaper is the only way to handle them consistently.

### Implementation Priority

| Priority | Task | Effort | Dependencies |
|----------|------|--------|-------------|
| P0 | Create `FFmpegFilterEscaper` with full test suite | 0.5 day | None |
| P0 | Wire into `FFmpegCommandBuilder` | 0.25 day | P0 |
| P1 | Convert filter modules to `FilterSpec` pattern | 0.5 day | P0 |
| P1 | Add `FilterSpec`/`FilterGraph` dataclasses | 0.25 day | P0 |
| P2 | Add Phase C filter templates | 0.5 day | P1 |

### Acceptance Criteria

- All special characters (`:`, `,`, `;`, `=`, `[`, `]`, `\`, `'`, `%`, `{`, `}`, space) are escaped correctly
- Windows paths (`C:\Users\...`, `\\server\share`) produce valid filter strings
- `textfile=` is the default recommendation for AI-generated text
- Double-escaping is idempotent (calling escape twice produces the same result)
- All existing FFmpeg tests continue to pass
- New unit tests cover all edge cases
- No filter module bypasses the escaper
