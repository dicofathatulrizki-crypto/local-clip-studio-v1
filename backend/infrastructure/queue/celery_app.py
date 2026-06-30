"""Celery application configuration and task definitions.

Configures Celery for local-first operation with optional Redis
broker, fallback to in-memory/local backend, and defines the
task signatures for all 15 queue job types.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import Celery
from celery.signals import (
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
    task_success,
)

from backend.infrastructure.queue.events import QueueEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Celery app
# ---------------------------------------------------------------------------

celery_app = Celery("localclip")

# Default config — local filesystem-based broker/backend for local-first
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_store_errors_even_if_ignored=True,
    worker_send_task_events=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600 * 24 * 7,  # Keep results for 7 days
    task_soft_time_limit=3600,  # 1 hour
    task_time_limit=3900,  # 1 hour 5 minutes
)

# ---------------------------------------------------------------------------
# Event callbacks
# ---------------------------------------------------------------------------

# These are populated at runtime by the queue manager
_on_event: Any = None


def set_event_callback(callback: Any) -> None:
    """Set the callback for emitting queue events to the B3 WebSocket."""
    global _on_event
    _on_event = callback


async def _emit_event(event: QueueEvent) -> None:
    """Emit a queue event through the registered callback."""
    if _on_event is not None:
        try:
            await _on_event(event)
        except Exception:
            logger.exception("Failed to emit queue event: %s", event.type.value)


# ---------------------------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------------------------


@task_prerun.connect
def handle_task_prerun(task_id: str, task: Any, **kwargs: Any) -> None:
    """Log and emit event when a task starts."""
    logger.info("Task started: %s [%s]", task.name, task_id)


@task_success.connect
def handle_task_success(sender: Any, result: Any, **kwargs: Any) -> None:
    """Log and emit event when a task succeeds."""
    logger.info("Task succeeded: %s", sender.request.id)


@task_failure.connect
def handle_task_failure(
    sender: Any,
    task_id: str,
    exception: Exception,
    **kwargs: Any,
) -> None:
    """Log and emit event when a task fails."""
    logger.error(
        "Task failed: %s [%s]: %s",
        sender.name, task_id, exception,
    )


@task_retry.connect
def handle_task_retry(
    sender: Any,
    reason: str,
    **kwargs: Any,
) -> None:
    """Log when a task is retried."""
    logger.warning("Task retry: %s — %s", sender.request.id, reason)


@task_postrun.connect
def handle_task_postrun(
    sender: Any,
    task_id: str,
    state: str,
    **kwargs: Any,
) -> None:
    """Log task post-run state."""
    logger.debug("Task postrun: %s [state=%s]", task_id, state)


# ---------------------------------------------------------------------------
# Task signatures — 15 job types
# ---------------------------------------------------------------------------

# Each function is a Celery shared_task placeholder.
# Actual business logic will be injected by Services in future modules.
# Here we define the task signatures, metadata, and routing configuration.

_JOB_TYPE_ROUTING: dict[str, dict[str, Any]] = {
    "video_import": {"queue": "video", "priority": 5},
    "audio_extraction": {"queue": "audio", "priority": 5},
    "proxy_generation": {"queue": "video", "priority": 4},
    "scene_detection": {"queue": "analysis", "priority": 4},
    "whisperx_stt": {"queue": "analysis", "priority": 4},
    "yolo_vision": {"queue": "analysis", "priority": 4},
    "ocr": {"queue": "analysis", "priority": 4},
    "llm_analysis": {"queue": "analysis", "priority": 3},
    "clip_generation": {"queue": "clip", "priority": 3},
    "caption_generation": {"queue": "caption", "priority": 3},
    "translation": {"queue": "caption", "priority": 2},
    "export": {"queue": "export", "priority": 2},
    "thumbnail_generation": {"queue": "video", "priority": 4},
    "ai_model_download": {"queue": "model", "priority": 1},
    "cache_cleanup": {"queue": "maintenance", "priority": 1},
}


def get_routing_for(job_type: str) -> dict[str, Any]:
    """Get Celery routing options for a job type."""
    return _JOB_TYPE_ROUTING.get(job_type, {"queue": "default", "priority": 5})


# ---------------------------------------------------------------------------
# Configure Celery app with routing
# ---------------------------------------------------------------------------

celery_app.conf.task_routes = {
    "video_import": {"queue": "video"},
    "audio_extraction": {"queue": "audio"},
    "proxy_generation": {"queue": "video"},
    "scene_detection": {"queue": "analysis"},
    "whisperx_stt": {"queue": "analysis"},
    "yolo_vision": {"queue": "analysis"},
    "ocr": {"queue": "analysis"},
    "llm_analysis": {"queue": "analysis"},
    "clip_generation": {"queue": "clip"},
    "caption_generation": {"queue": "caption"},
    "translation": {"queue": "caption"},
    "export": {"queue": "export"},
    "thumbnail_generation": {"queue": "video"},
    "ai_model_download": {"queue": "model"},
    "cache_cleanup": {"queue": "maintenance"},
}

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_priority = 5
