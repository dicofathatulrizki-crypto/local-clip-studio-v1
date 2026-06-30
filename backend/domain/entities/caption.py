"""Caption entity — a timed caption track for a clip.

Business rules:
    - Each clip can have multiple caption tracks (one per language)
    - Source language track is marked as ``is_source_language=True``
    - Caption timing must align with clip boundaries
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.domain.exceptions import DomainValidationError
from backend.domain.value_objects import CaptionId, ClipId, Language


@dataclass
class Caption:
    """A caption track for a clip.

    Attributes:
        id: Unique caption track identifier.
        clip_id: Identifier of the associated clip.
        language: Language code (ISO 639-1, e.g., 'en', 'es').
        style: Caption styling configuration (font, size, color, position).
        captions: List of caption segments with timing and text.
        is_source_language: Whether this is the original source language track.
        created_at: Timestamp of creation.
    """

    id: CaptionId = field(default_factory=CaptionId)
    clip_id: ClipId | None = None
    language: str = Language.EN.value
    style: dict[str, Any] = field(default_factory=dict)
    captions: list[dict[str, Any]] = field(default_factory=list)
    is_source_language: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Validate caption invariants."""
        if not Language.is_supported(self.language):
            raise DomainValidationError(
                f"Unsupported language code: '{self.language}'",
                {"language": self.language, "supported": list(Language)},
            )

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------

    def set_captions(self, captions: list[dict[str, Any]]) -> None:
        """Set the caption segments.

        Each caption segment should have at least ``start_ms``, ``end_ms``,
        and ``text`` keys.
        """
        self.captions = captions

    def set_style(self, style: dict[str, Any]) -> None:
        """Set the caption styling configuration.

        Typical style keys:
        - ``font_family``: Font name
        - ``font_size``: Font size in pixels
        - ``color``: Text color (hex)
        - ``background_color``: Background color (hex)
        - ``position``: 'top', 'bottom', or 'custom'
        - ``outline_color``: Outline color (hex)
        - ``animation``: Animation style name
        """
        self.style = style

    def add_caption_segment(
        self,
        start_ms: int,
        end_ms: int,
        text: str,
        words: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add a single caption segment.

        Args:
            start_ms: Start timestamp in milliseconds.
            end_ms: End timestamp in milliseconds.
            text: Caption text.
            words: Optional word-level timing for karaoke effects.
        """
        segment: dict[str, Any] = {
            "start_ms": start_ms,
            "end_ms": end_ms,
            "text": text,
        }
        if words:
            segment["words"] = words
        self.captions.append(segment)

    def mark_as_translation(self) -> None:
        """Mark this caption track as a translation (not source language)."""
        self.is_source_language = False

    @property
    def language_name(self) -> str:
        """Return the full language name (lowercase)."""
        lang_map = {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "ja": "Japanese",
            "ko": "Korean",
            "zh": "Chinese",
            "ar": "Arabic",
            "hi": "Hindi",
        }
        return lang_map.get(self.language, self.language)

    @property
    def is_translation(self) -> bool:
        """Check if this track is a translated caption."""
        return not self.is_source_language
