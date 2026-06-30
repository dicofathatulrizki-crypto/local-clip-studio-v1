"""Unit tests for Caption entity."""

from __future__ import annotations

import pytest

from backend.domain.entities import Caption
from backend.domain.exceptions import DomainValidationError
from backend.domain.value_objects import Language


class TestCaptionCreation:
    def test_create_default(self) -> None:
        caption = Caption()
        assert caption.language == Language.EN.value
        assert caption.is_source_language
        assert caption.captions == []

    def test_create_translation(self) -> None:
        caption = Caption(language=Language.ES.value, is_source_language=False)
        assert caption.language == "es"
        assert not caption.is_source_language
        assert caption.is_translation

    def test_unsupported_language_raises(self) -> None:
        with pytest.raises(DomainValidationError):
            Caption(language="xx")


class TestCaptionBehaviour:
    def test_set_captions(self) -> None:
        caption = Caption()
        captions = [
            {"start_ms": 0, "end_ms": 1000, "text": "Hello"},
            {"start_ms": 1000, "end_ms": 2000, "text": "World"},
        ]
        caption.set_captions(captions)
        assert len(caption.captions) == 2

    def test_set_style(self) -> None:
        caption = Caption()
        style = {
            "font_family": "Arial",
            "font_size": 24,
            "color": "#ffffff",
            "position": "bottom",
        }
        caption.set_style(style)
        assert caption.style["font_family"] == "Arial"

    def test_add_caption_segment(self) -> None:
        caption = Caption()
        caption.add_caption_segment(0, 1000, "Hello", [
            {"word": "Hello", "start_ms": 0, "end_ms": 500},
        ])
        assert len(caption.captions) == 1
        assert caption.captions[0]["text"] == "Hello"
        assert "words" in caption.captions[0]

    def test_add_caption_segment_without_words(self) -> None:
        caption = Caption()
        caption.add_caption_segment(0, 1000, "Hello")
        assert "words" not in caption.captions[0]

    def test_mark_as_translation(self) -> None:
        caption = Caption()
        assert caption.is_source_language
        caption.mark_as_translation()
        assert not caption.is_source_language

    def test_language_name(self) -> None:
        assert Caption(language="en").language_name == "English"
        assert Caption(language="es").language_name == "Spanish"
        assert Caption(language="fr").language_name == "French"
