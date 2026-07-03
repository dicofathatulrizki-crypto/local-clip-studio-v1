"""FFmpegFilterEscaper — centralized FFmpeg filter argument escaping.

All FFmpeg filter graph strings built by CommandBuilder must pass their
user-supplied or file-path values through these methods before constructing
the -vf/-af/-filter_complex argument.

Every method is:
  - Deterministic: same input always produces same output.
  - Idempotent: escape(x) == escape(escape(x)) for all valid x.
  - Pure: no I/O, no side effects, no state.
  - Stateless: no caching, no global state, no mutable shared state.
"""
from __future__ import annotations


class FFmpegFilterEscaper:
    """Centralized FFmpeg filter argument escaping.

    Usage:
        escaped = FFmpegFilterEscaper.escape_filter_value("path:value")
        assert escaped == "path\\:value"
    """

    # Characters with special meaning in FFmpeg filtergraph syntax.
    # Backslash is included because it is the escape character itself.
    _SPECIAL_CHARS = frozenset('\\:;,=[]\'')

    @staticmethod
    def escape_filter_value(value: str | int | float) -> str:
        """Escape a value for use in -vf/-af/-filter_complex filter arguments.

        Escapes: \\ : , ; = [ ] '
        Idempotent: applying twice produces the same result.
        Achieved by scanning character-by-character and preserving
        already-escaped sequences (backslash + special char) as-is.

        Args:
            value: The filter parameter value to escape.

        Returns:
            The escaped string, safe for embedding in a filtergraph string.
        """
        s = str(value)
        result: list[str] = []
        i = 0
        while i < len(s):
            ch = s[i]
            # If this is a backslash AND the next character is a special
            # character, the sequence is already escaped — preserve it.
            if ch == '\\' and i + 1 < len(s) and s[i + 1] in FFmpegFilterEscaper._SPECIAL_CHARS:
                result.append(ch)
                result.append(s[i + 1])
                i += 2
            elif ch in FFmpegFilterEscaper._SPECIAL_CHARS:
                # Unescaped special character — prefix with backslash.
                result.append('\\')
                result.append(ch)
                i += 1
            else:
                result.append(ch)
                i += 1
        return ''.join(result)

    @staticmethod
    def escape_filter_path(path: str) -> str:
        """Escape a filesystem path for use in FFmpeg filter arguments.

        Normalises backslashes to forward slashes for cross-platform
        compatibility (Windows -> Linux/macOS), then escapes colons
        which are filter parameter separators.

        Designed for raw filesystem paths (not pre-escaped strings).
        Idempotent for valid filesystem paths because after normalisation
        there are no backslashes left to conflict with the colon escape.

        Args:
            path: The filesystem path to escape.

        Returns:
            The escaped path, safe for embedding in a filtergraph string.
        """
        # Step 1: Normalise backslashes to forward slashes (Windows compat)
        normalized = path.replace('\\', '/')
        # Step 2: Escape colons — no backslashes remain, so no conflict
        escaped = normalized.replace(':', '\\:')
        return escaped

    @staticmethod
    def escape_drawtext_text(text: str) -> str:
        """Escape text for the drawtext filter's text= parameter.

        Applies full filtergraph escaping first, then additionally escapes
        the special drawtext expression markers: % { }

        Prefer using textfile= instead to bypass escaping entirely.

        Args:
            text: The text content to display via drawtext.

        Returns:
            The double-escaped text string.
        """
        # Step 1: Apply standard filtergraph escaping
        escaped = FFmpegFilterEscaper.escape_filter_value(text)
        # Step 2: Escape drawtext-specific expression markers
        escaped = escaped.replace('%', '\\%')
        escaped = escaped.replace('{', '\\{')
        escaped = escaped.replace('}', '\\}')
        return escaped

    @staticmethod
    def normalize_path_for_ffmpeg(path: str) -> str:
        """Normalise a filesystem path for use with FFmpeg.

        Replaces Windows backslash separators with forward slashes
        for consistent cross-platform behaviour.

        Args:
            path: The filesystem path to normalise.

        Returns:
            The normalised path with forward slashes.
        """
        return path.replace('\\', '/')
