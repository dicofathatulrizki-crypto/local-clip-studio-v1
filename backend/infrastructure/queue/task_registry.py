"""Task registry — job type registration, lookup, and routing.

Maps task types to their TaskDefinitions and handler callables.
Supports dynamic registration and querying of available task types.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.queue.exceptions import QueueError
from backend.infrastructure.queue.models import (
    JobRecord,
    RetryPolicy,
    TaskDefinition,
)

logger = get_logger(__name__)

# Type for async job handler
JobHandler = Callable[[JobRecord], Coroutine[Any, Any, dict[str, Any]]]


class TaskRegistry:
    """Registry for job types, their definitions, and handler functions.

    Supports registering handlers for each task type, querying
    definitions, and looking up handlers at dispatch time.

    Usage:
        registry = TaskRegistry()
        registry.register("video_import", handler_fn, TaskDefinition(...))
        handler = registry.get_handler("video_import")
        definition = registry.get_definition("video_import")
    """

    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}
        self._definitions: dict[str, TaskDefinition] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        task_type: str,
        handler: JobHandler,
        definition: TaskDefinition | None = None,
    ) -> None:
        """Register a task type with its handler and definition.

        Args:
            task_type: Unique task type identifier
            handler: Async callable that processes the job
            definition: Task configuration (uses defaults if not provided)
        """
        if task_type in self._handlers:
            logger.warning(
                "task_type_re_registered",
                extra={"task_type": task_type},
            )

        self._handlers[task_type] = handler
        self._definitions[task_type] = definition or TaskDefinition(
            task_type=task_type,
            retry_policy=RetryPolicy(),
        )

        logger.info(
            "task_type_registered",
            extra={
                "task_type": task_type,
                "timeout": definition.timeout_seconds if definition else 3600,
            },
        )

    def unregister(self, task_type: str) -> bool:
        """Unregister a task type.

        Args:
            task_type: Task type to remove

        Returns:
            True if removed, False if not found
        """
        if task_type not in self._handlers:
            return False
        del self._handlers[task_type]
        del self._definitions[task_type]
        logger.info("task_type_unregistered", extra={"task_type": task_type})
        return True

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_handler(self, task_type: str) -> JobHandler:
        """Get the handler for a task type.

        Args:
            task_type: Task type to look up

        Returns:
            The registered handler function

        Raises:
            QueueError: If task type is not registered
        """
        handler = self._handlers.get(task_type)
        if handler is None:
            raise QueueError(
                "ERR-QUEUE-UNKNOWN-TASK",
                f"Unknown task type: '{task_type}'",
                {"task_type": task_type},
            )
        return handler

    def get_definition(self, task_type: str) -> TaskDefinition:
        """Get the definition for a task type.

        Args:
            task_type: Task type to look up

        Returns:
            The registered TaskDefinition

        Raises:
            QueueError: If task type is not registered
        """
        definition = self._definitions.get(task_type)
        if definition is None:
            raise QueueError(
                "ERR-QUEUE-UNKNOWN-TASK",
                f"Unknown task type: '{task_type}'",
                {"task_type": task_type},
            )
        return definition

    def is_registered(self, task_type: str) -> bool:
        """Check if a task type is registered.

        Args:
            task_type: Task type to check

        Returns:
            True if registered
        """
        return task_type in self._handlers

    def list_task_types(self) -> list[str]:
        """List all registered task types.

        Returns:
            Sorted list of task type identifiers
        """
        return sorted(self._handlers.keys())

    def list_definitions(self) -> list[TaskDefinition]:
        """List all registered task definitions.

        Returns:
            List of TaskDefinition objects
        """
        return [self._definitions[t] for t in sorted(self._definitions)]

    # ------------------------------------------------------------------
    # Default task type registrations
    # ------------------------------------------------------------------

    @staticmethod
    def create_default_definitions() -> dict[str, TaskDefinition]:
        """Create default TaskDefinitions for all supported job types.

        Returns:
            Dict mapping task type → TaskDefinition with appropriate defaults
        """
        return {
            "video_import": TaskDefinition(
                task_type="video_import",
                description="Import a video file into a project",
                timeout_seconds=7200,
                max_concurrency=2,
                retry_policy=RetryPolicy(max_retries=2, base_delay_seconds=30),
                resource_requirements=["disk_io"],
            ),
            "audio_extraction": TaskDefinition(
                task_type="audio_extraction",
                description="Extract audio from a video file",
                timeout_seconds=1800,
                max_concurrency=4,
                retry_policy=RetryPolicy(max_retries=2),
                resource_requirements=["ffmpeg"],
            ),
            "proxy_generation": TaskDefinition(
                task_type="proxy_generation",
                description="Generate a low-res proxy video",
                timeout_seconds=3600,
                max_concurrency=2,
                retry_policy=RetryPolicy(max_retries=2),
                resource_requirements=["ffmpeg", "gpu"],
            ),
            "scene_detection": TaskDefinition(
                task_type="scene_detection",
                description="Detect scene changes in a video",
                timeout_seconds=1800,
                max_concurrency=2,
                retry_policy=RetryPolicy(max_retries=2),
                resource_requirements=["ffmpeg"],
            ),
            "stt": TaskDefinition(
                task_type="stt",
                description="Speech-to-text using WhisperX",
                timeout_seconds=7200,
                max_concurrency=1,
                retry_policy=RetryPolicy(max_retries=2, base_delay_seconds=60),
                resource_requirements=["gpu", "model_stt"],
            ),
            "vision": TaskDefinition(
                task_type="vision",
                description="Visual analysis using YOLO",
                timeout_seconds=3600,
                max_concurrency=1,
                retry_policy=RetryPolicy(max_retries=2, base_delay_seconds=60),
                resource_requirements=["gpu", "model_vision"],
            ),
            "ocr": TaskDefinition(
                task_type="ocr",
                description="Optical character recognition",
                timeout_seconds=1800,
                max_concurrency=2,
                retry_policy=RetryPolicy(max_retries=2),
                resource_requirements=["gpu", "model_ocr"],
            ),
            "llm_analysis": TaskDefinition(
                task_type="llm_analysis",
                description="LLM-based content analysis",
                timeout_seconds=1800,
                max_concurrency=1,
                retry_policy=RetryPolicy(max_retries=3, base_delay_seconds=30, backoff_multiplier=1.5),
                resource_requirements=["gpu", "model_llm"],
            ),
            "clip_generation": TaskDefinition(
                task_type="clip_generation",
                description="Generate clip candidates from analysis",
                timeout_seconds=600,
                max_concurrency=2,
                retry_policy=RetryPolicy(max_retries=1),
                resource_requirements=["cpu"],
            ),
            "caption_generation": TaskDefinition(
                task_type="caption_generation",
                description="Generate captions/subtitles for a clip",
                timeout_seconds=600,
                max_concurrency=4,
                retry_policy=RetryPolicy(max_retries=2),
                resource_requirements=["cpu"],
            ),
            "translation": TaskDefinition(
                task_type="translation",
                description="Translate captions to another language",
                timeout_seconds=600,
                max_concurrency=2,
                retry_policy=RetryPolicy(max_retries=3),
                resource_requirements=["gpu", "model_llm"],
            ),
            "export": TaskDefinition(
                task_type="export",
                description="Render a clip to output format",
                timeout_seconds=7200,
                max_concurrency=1,
                retry_policy=RetryPolicy(max_retries=1, base_delay_seconds=30),
                resource_requirements=["ffmpeg", "gpu"],
            ),
            "thumbnail_generation": TaskDefinition(
                task_type="thumbnail_generation",
                description="Generate video thumbnails",
                timeout_seconds=300,
                max_concurrency=4,
                retry_policy=RetryPolicy(max_retries=2),
                resource_requirements=["ffmpeg"],
            ),
            "model_download": TaskDefinition(
                task_type="model_download",
                description="Download an AI model file",
                timeout_seconds=7200,
                max_concurrency=1,
                retry_policy=RetryPolicy(max_retries=3, base_delay_seconds=30, backoff_multiplier=1.0),
                resource_requirements=["network", "disk_io"],
            ),
            "cache_cleanup": TaskDefinition(
                task_type="cache_cleanup",
                description="Clean up expired cache files",
                timeout_seconds=600,
                max_concurrency=1,
                retry_policy=RetryPolicy(max_retries=1),
                resource_requirements=["cpu"],
            ),
        }
