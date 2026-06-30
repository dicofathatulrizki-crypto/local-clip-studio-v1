"""Immutable value objects for Local Clip Studio.

Value objects are defined by their attributes, not identity. Two value
objects with the same attributes are considered equal. All value objects
are ``frozen=True`` dataclasses (immutable).

Architecture:
    - Zero imports from infrastructure
    - All objects are hashable and comparable
    - Built-in validation on construction
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.domain.exceptions import (
    DomainValidationError,
    InvalidQualityScoreError,
    InvalidTimestampError,
    InvalidVideoFormatError,
)

# ---------------------------------------------------------------------------
# Supported constants
# ---------------------------------------------------------------------------

SUPPORTED_VIDEO_EXTENSIONS: set[str] = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
SUPPORTED_VIDEO_CODECS: set[str] = {"h264", "h265", "hevc", "vp9", "prores", "av1"}
SUPPORTED_AUDIO_CODECS: set[str] = {"aac", "mp3", "opus", "pcm_s16le", "flac", "vorbis"}
SUPPORTED_EXPORT_FORMATS: set[str] = {"mp4", "mov", "webm", "srt", "vtt", "ass", "edl", "xml", "json"}
SUPPORTED_LANGUAGES: set[str] = {
    "en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh",
    "ar", "hi", "nl", "pl", "tr", "th", "vi", "sv", "da", "fi",
}
MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024 * 1024  # 50 GB
MIN_CLIP_DURATION_MS: int = 3_000  # 3 seconds
MAX_CLIP_DURATION_MS: int = 90_000  # 90 seconds
QUALITY_SCORE_MIN: int = 0
QUALITY_SCORE_MAX: int = 100


# ---------------------------------------------------------------------------
# Simple identifier value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectId:
    """Identifies a unique project.

    Wraps a UUID string. Validates non-empty format on construction.
    """

    value: str = ""

    def __post_init__(self) -> None:
        if not self.value:
            object.__setattr__(self, "value", self._generate())
        elif not self.value.strip():
            raise DomainValidationError("ProjectId cannot be empty")

    @staticmethod
    def _generate() -> str:
        """Generate a simple unique ID (no uuid import needed)."""
        import random

        return (
            f"{int(time.time() * 1_000_000):020x}-"
            f"{random.getrandbits(64):016x}"
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class VideoId:
    """Identifies a unique video (shared across projects)."""

    value: str = ""

    def __post_init__(self) -> None:
        if not self.value:
            object.__setattr__(self, "value", self._generate())
        elif not self.value.strip():
            raise DomainValidationError("VideoId cannot be empty")

    @staticmethod
    def _generate() -> str:
        import random

        return (
            f"{int(time.time() * 1_000_000):020x}-"
            f"{random.getrandbits(64):016x}"
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ClipId:
    """Identifies a unique clip candidate."""

    value: str = ""

    def __post_init__(self) -> None:
        if not self.value:
            object.__setattr__(self, "value", self._generate())
        elif not self.value.strip():
            raise DomainValidationError("ClipId cannot be empty")

    @staticmethod
    def _generate() -> str:
        import random

        return (
            f"{int(time.time() * 1_000_000):020x}-"
            f"{random.getrandbits(64):016x}"
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class AnalysisId:
    """Identifies a unique analysis record."""

    value: str = ""

    def __post_init__(self) -> None:
        if not self.value:
            object.__setattr__(self, "value", self._generate())
        elif not self.value.strip():
            raise DomainValidationError("AnalysisId cannot be empty")

    @staticmethod
    def _generate() -> str:
        import random

        return (
            f"{int(time.time() * 1_000_000):020x}-"
            f"{random.getrandbits(64):016x}"
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ExportId:
    """Identifies a unique export job."""

    value: str = ""

    def __post_init__(self) -> None:
        if not self.value:
            object.__setattr__(self, "value", self._generate())
        elif not self.value.strip():
            raise DomainValidationError("ExportId cannot be empty")

    @staticmethod
    def _generate() -> str:
        import random

        return (
            f"{int(time.time() * 1_000_000):020x}-"
            f"{random.getrandbits(64):016x}"
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class CaptionId:
    """Identifies a unique caption track."""

    value: str = ""

    def __post_init__(self) -> None:
        if not self.value:
            object.__setattr__(self, "value", self._generate())
        elif not self.value.strip():
            raise DomainValidationError("CaptionId cannot be empty")

    @staticmethod
    def _generate() -> str:
        import random

        return (
            f"{int(time.time() * 1_000_000):020x}-"
            f"{random.getrandbits(64):016x}"
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ProviderId:
    """Identifies a unique AI provider."""

    value: str = ""

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise DomainValidationError("ProviderId cannot be empty")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class PluginId:
    """Identifies a unique plugin by name."""

    value: str = ""

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise DomainValidationError("PluginId cannot be empty")

    def __str__(self) -> str:
        return self.value


# ---------------------------------------------------------------------------
# Media-related value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Duration:
    """Duration in milliseconds. Must be non-negative."""

    milliseconds: int = 0

    def __post_init__(self) -> None:
        if self.milliseconds < 0:
            raise InvalidTimestampError(
                "Duration cannot be negative",
                {"milliseconds": self.milliseconds},
            )

    @property
    def seconds(self) -> float:
        """Convert to seconds."""
        return self.milliseconds / 1000.0

    @property
    def minutes(self) -> float:
        """Convert to minutes."""
        return self.seconds / 60.0

    @property
    def as_hms(self) -> str:
        """Return HH:MM:SS format."""
        total_seconds = int(self.milliseconds / 1000)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def __add__(self, other: Duration) -> Duration:
        return Duration(milliseconds=self.milliseconds + other.milliseconds)

    def __sub__(self, other: Duration) -> Duration:
        return Duration(milliseconds=self.milliseconds - other.milliseconds)

    def __lt__(self, other: Duration) -> bool:
        return self.milliseconds < other.milliseconds

    def __le__(self, other: Duration) -> bool:
        return self.milliseconds <= other.milliseconds

    def __gt__(self, other: Duration) -> bool:
        return self.milliseconds > other.milliseconds

    def __ge__(self, other: Duration) -> bool:
        return self.milliseconds >= other.milliseconds


@dataclass(frozen=True)
class TimestampRange:
    """A range of time defined by start and end milliseconds.

    Validates that start < end, and that the range meets minimum duration.
    """

    start_ms: int = 0
    end_ms: int = 0
    min_duration_ms: int = MIN_CLIP_DURATION_MS

    def __post_init__(self) -> None:
        if self.start_ms < 0 or self.end_ms < 0:
            raise InvalidTimestampError(
                "Timestamps cannot be negative",
                {"start_ms": self.start_ms, "end_ms": self.end_ms},
            )
        if self.start_ms >= self.end_ms:
            raise InvalidTimestampError(
                "Start must be before end",
                {"start_ms": self.start_ms, "end_ms": self.end_ms},
            )
        duration = self.end_ms - self.start_ms
        if duration < self.min_duration_ms:
            raise InvalidTimestampError(
                f"Duration ({duration}ms) is below minimum ({self.min_duration_ms}ms)",
                {"duration_ms": duration, "min_duration_ms": self.min_duration_ms},
            )

    @property
    def duration_ms(self) -> int:
        """Total duration in milliseconds."""
        return self.end_ms - self.start_ms

    @property
    def duration(self) -> Duration:
        """Duration as a value object."""
        return Duration(milliseconds=self.duration_ms)

    def contains(self, timestamp_ms: int) -> bool:
        """Check if a timestamp falls within this range (inclusive)."""
        return self.start_ms <= timestamp_ms <= self.end_ms

    def overlaps(self, other: TimestampRange) -> bool:
        """Check if this range overlaps with another."""
        return self.start_ms < other.end_ms and other.start_ms < self.end_ms

    def merge(self, other: TimestampRange) -> TimestampRange:
        """Merge overlapping or adjacent ranges into one."""
        if not self.overlaps(other) and self.end_ms != other.start_ms:
            raise InvalidTimestampError(
                "Cannot merge non-overlapping ranges",
                {"range1": str(self), "range2": str(other)},
            )
        return TimestampRange(
            start_ms=min(self.start_ms, other.start_ms),
            end_ms=max(self.end_ms, other.end_ms),
            min_duration_ms=min(self.min_duration_ms, other.min_duration_ms),
        )

    def __str__(self) -> str:
        return f"[{self.start_ms}ms → {self.end_ms}ms]"


@dataclass(frozen=True)
class Resolution:
    """Video resolution (width × height). Both dimensions must be positive."""

    width: int = 0
    height: int = 0

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise DomainValidationError(
                "Resolution dimensions must be positive",
                {"width": self.width, "height": self.height},
            )

    @property
    def aspect_ratio(self) -> AspectRatio:
        """Calculate the aspect ratio."""
        from math import gcd

        g = gcd(self.width, self.height)
        return AspectRatio(
            width_ratio=self.width // g,
            height_ratio=self.height // g,
        )

    @property
    def is_landscape(self) -> bool:
        """Check if the resolution is landscape-oriented."""
        return self.width > self.height

    @property
    def is_portrait(self) -> bool:
        """Check if the resolution is portrait-oriented."""
        return self.height > self.width

    @property
    def is_square(self) -> bool:
        """Check if the resolution is square."""
        return self.width == self.height

    @property
    def megapixels(self) -> float:
        """Total pixel count in megapixels."""
        return (self.width * self.height) / 1_000_000.0

    def __str__(self) -> str:
        return f"{self.width}x{self.height}"


@dataclass(frozen=True)
class AspectRatio:
    """An immutable aspect ratio (e.g., 16:9, 9:16, 4:3, 1:1)."""

    width_ratio: int = 16
    height_ratio: int = 9

    def __post_init__(self) -> None:
        if self.width_ratio <= 0 or self.height_ratio <= 0:
            raise DomainValidationError(
                "Aspect ratio components must be positive",
                {"width_ratio": self.width_ratio, "height_ratio": self.height_ratio},
            )

    @property
    def ratio(self) -> float:
        """Return the floating-point ratio."""
        return self.width_ratio / self.height_ratio

    @property
    def is_landscape(self) -> bool:
        """Check if this is a landscape ratio."""
        return self.width_ratio > self.height_ratio

    @property
    def is_portrait(self) -> bool:
        """Check if this is a portrait ratio."""
        return self.height_ratio > self.width_ratio

    @property
    def is_square(self) -> bool:
        """Check if this is a square ratio."""
        return self.width_ratio == self.height_ratio

    def __str__(self) -> str:
        return f"{self.width_ratio}:{self.height_ratio}"


@dataclass(frozen=True)
class FrameRate:
    """Frame rate expressed as frames per second. Must be positive."""

    fps: float = 0.0

    def __post_init__(self) -> None:
        if self.fps <= 0:
            raise DomainValidationError(
                "Frame rate must be positive",
                {"fps": self.fps},
            )

    @property
    def duration_per_frame_ms(self) -> float:
        """Duration of a single frame in milliseconds."""
        return 1000.0 / self.fps

    def __str__(self) -> str:
        return f"{self.fps:.2f} fps"

    def __float__(self) -> float:
        return self.fps


# ---------------------------------------------------------------------------
# File-related value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileHash:
    """SHA-256 hash of a file for deduplication and integrity verification.

    Validates the hash is a valid 64-character hexadecimal string.
    """

    value: str = ""

    def __post_init__(self) -> None:
        if not self.value:
            object.__setattr__(self, "value", self._generate_empty_hash())
        elif not re.match(r"^[a-f0-9]{64}$", self.value):
            raise DomainValidationError(
                "FileHash must be a 64-character hex string",
                {"hash": self.value},
            )

    @staticmethod
    def _generate_empty_hash() -> str:
        return hashlib.sha256(b"").hexdigest()

    @property
    def prefix(self) -> str:
        """First 16 characters of the hash (used for filenames)."""
        return self.value[:16]

    def __str__(self) -> str:
        return self.value

    def verify_file(self, file_path: str, chunk_size: int = 65_536) -> bool:
        """Verify a file's SHA-256 hash matches this value.

        Args:
            file_path: Path to the file to verify.
            chunk_size: Read buffer size in bytes.

        Returns:
            True if the file's hash matches, False otherwise.
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest() == self.value


@dataclass(frozen=True)
class FilePath:
    """A validated file path within the application's allowed directory.

    Guards against path traversal by ensuring the resolved path is
    within the allowed base directory.
    """

    path: str = ""
    allowed_base: str | None = None

    def __post_init__(self) -> None:
        if not self.path:
            raise DomainValidationError("FilePath cannot be empty")

    @property
    def extension(self) -> str:
        """File extension including the dot (e.g., '.mp4')."""
        _, ext = os.path.splitext(self.path)
        return ext.lower()

    @property
    def filename(self) -> str:
        """File name with extension."""
        return os.path.basename(self.path)

    @property
    def stem(self) -> str:
        """File name without extension."""
        return os.path.splitext(os.path.basename(self.path))[0]

    @property
    def directory(self) -> str:
        """Parent directory of the file."""
        return os.path.dirname(self.path)

    def is_within(self, base_path: str) -> bool:
        """Check if this path is within the given base directory."""
        resolved_path = os.path.realpath(self.path)
        resolved_base = os.path.realpath(base_path)
        return resolved_path.startswith(resolved_base + os.sep)

    def resolve(self) -> str:
        """Return the resolved (real) path, checking for traversal."""
        if self.allowed_base:
            resolved = os.path.realpath(self.path)
            resolved_base = os.path.realpath(self.allowed_base)
            if not resolved.startswith(resolved_base + os.sep) and resolved != resolved_base:
                raise DomainValidationError(
                    "Path traversal detected",
                    {"path": self.path, "allowed_base": self.allowed_base},
                )
        return os.path.realpath(self.path)

    def is_video(self) -> bool:
        """Check if the file extension is a supported video format."""
        return self.extension in SUPPORTED_VIDEO_EXTENSIONS


# ---------------------------------------------------------------------------
# Quality score value object  (SRS §6 — Quality Score Dimensions)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityScoreDimensions:
    """Individual quality score dimension values (0-100 each).

    Dimensions (per Vision Document §6):
    - ``hook_strength`` (25 %): Compelling opening within first 3 seconds
    - ``content_density`` (20 %): Information density per second
    - ``audio_clarity`` (15 %): Speech clarity, noise floor
    - ``visual_variety`` (15 %): Shot changes, camera movement
    - ``structural_completeness`` (15 %): Beginning, middle, and end
    - ``engagement_potential`` (10 %): Predicted retention
    """

    hook_strength: int = 0
    content_density: int = 0
    audio_clarity: int = 0
    visual_variety: int = 0
    structural_completeness: int = 0
    engagement_potential: int = 0

    _weights: dict[str, float] = field(
        default_factory=lambda: {
            "hook_strength": 0.25,
            "content_density": 0.20,
            "audio_clarity": 0.15,
            "visual_variety": 0.15,
            "structural_completeness": 0.15,
            "engagement_potential": 0.10,
        },
        compare=False,
        hash=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        for field_name, value in self._values().items():
            if not (QUALITY_SCORE_MIN <= value <= QUALITY_SCORE_MAX):
                raise InvalidQualityScoreError(
                    f"Dimension '{field_name}' must be between "
                    f"{QUALITY_SCORE_MIN} and {QUALITY_SCORE_MAX}",
                    {"field": field_name, "value": value},
                )

    def _values(self) -> dict[str, int]:
        return {
            "hook_strength": self.hook_strength,
            "content_density": self.content_density,
            "audio_clarity": self.audio_clarity,
            "visual_variety": self.visual_variety,
            "structural_completeness": self.structural_completeness,
            "engagement_potential": self.engagement_potential,
        }

    def weighted_average(self) -> float:
        """Calculate the weighted average of all dimensions.

        Returns a float between 0 and 100.
        """
        total = 0.0
        for name, value in self._values().items():
            total += value * self._weights[name]
        return total


@dataclass(frozen=True)
class QualityScore:
    """Composite quality score for a clip candidate.

    Wraps ``QualityScoreDimensions`` and provides the weighted overall
    score. A single overall score (0-100) can also be used.
    """

    overall: int = 0
    dimensions: QualityScoreDimensions | None = None

    def __post_init__(self) -> None:
        if not (QUALITY_SCORE_MIN <= self.overall <= QUALITY_SCORE_MAX):
            raise InvalidQualityScoreError(
                f"Overall quality score must be between "
                f"{QUALITY_SCORE_MIN} and {QUALITY_SCORE_MAX}",
                {"overall": self.overall},
            )

    @classmethod
    def from_dimensions(cls, dimensions: QualityScoreDimensions) -> QualityScore:
        """Create a QualityScore from dimensions using weighted average."""
        overall = round(dimensions.weighted_average())
        return cls(overall=overall, dimensions=dimensions)

    def __str__(self) -> str:
        return f"{self.overall}/100"


# ---------------------------------------------------------------------------
# Language and Format enums
# ---------------------------------------------------------------------------


class Language(str, Enum):
    """Supported language codes (ISO 639-1)."""

    EN = "en"
    ES = "es"
    FR = "fr"
    DE = "de"
    IT = "it"
    PT = "pt"
    RU = "ru"
    JA = "ja"
    KO = "ko"
    ZH = "zh"
    AR = "ar"
    HI = "hi"
    NL = "nl"
    PL = "pl"
    TR = "tr"
    TH = "th"
    VI = "vi"
    SV = "sv"
    DA = "da"
    FI = "fi"

    @classmethod
    def is_supported(cls, code: str) -> bool:
        """Check if a language code is supported."""
        return code.lower() in SUPPORTED_LANGUAGES


class ExportFormat(str, Enum):
    """Supported export output formats."""

    MP4 = "mp4"
    MOV = "mov"
    WEBM = "webm"
    SRT = "srt"
    VTT = "vtt"
    ASS = "ass"
    EDL = "edl"
    XML = "xml"
    JSON = "json"

    @classmethod
    def is_video(cls, fmt: str) -> bool:
        """Check if the format is a video format."""
        return fmt in {cls.MP4.value, cls.MOV.value, cls.WEBM.value}

    @classmethod
    def is_subtitle(cls, fmt: str) -> bool:
        """Check if the format is a subtitle format."""
        return fmt in {cls.SRT.value, cls.VTT.value, cls.ASS.value}

    @classmethod
    def is_interchange(cls, fmt: str) -> bool:
        """Check if the format is an interchange/XML format."""
        return fmt in {cls.EDL.value, cls.XML.value, cls.JSON.value}
