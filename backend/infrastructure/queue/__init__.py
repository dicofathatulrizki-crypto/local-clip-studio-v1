"""Queue infrastructure for background job processing.

Provides:
- Celery-based background execution with in-memory fallback
- Job priorities with sorted queue processing
- Job cancellation with resource cleanup
- Retry policies with exponential backoff
- Progress reporting integrated with B3 WebSocket
- Job persistence and queue recovery after restart
- Worker lifecycle management
- Concurrency control and resource locking
- Health monitoring and metrics collection
- Structured logging with correlation IDs

Architecture:
- Pure infrastructure layer — no business logic
- Integrates with all Phase A modules
- Progress events emitted via B3 WebSocket Manager
- Queue events raised for job lifecycle changes
"""

from __future__ import annotations

from backend.infrastructure.queue.cancellation import CancellationManager
from backend.infrastructure.queue.dispatcher import Dispatcher
from backend.infrastructure.queue.events import QueueEvent, QueueEventType
from backend.infrastructure.queue.exceptions import (
    CancellationError,
    DispatcherFullError,
    DuplicateJobError,
    JobNotFoundError,
    QueueError,
    QueueFullError,
    ResourceLockedError,
    WorkerNotRunningError,
    WorkerTimeoutError,
)
from backend.infrastructure.queue.health import HealthMonitor
from backend.infrastructure.queue.metrics import MetricsCollector
from backend.infrastructure.queue.models import (
    JobMetadata,
    JobPriority,
    JobStatus,
    QueueItem,
    QueuedJob,
    QueueSettings,
    RetryPolicy,
    TaskDefinition,
)
from backend.infrastructure.queue.priority import PriorityQueue
from backend.infrastructure.queue.progress import ProgressTracker, ProgressReporter
from backend.infrastructure.queue.retry import RetryManager
from backend.infrastructure.queue.scheduler import Scheduler
from backend.infrastructure.queue.task_registry import TaskRegistry
from backend.infrastructure.queue.worker import WorkerPool

__all__ = [
    "CancellationManager",
    "Dispatcher",
    "HealthMonitor",
    "MetricsCollector",
    "PriorityQueue",
    "ProgressTracker",
    "ProgressReporter",
    "QueueEvent",
    "QueueEventType",
    "RetryManager",
    "Scheduler",
    "TaskRegistry",
    "WorkerPool",
    # Models
    "JobMetadata",
    "JobPriority",
    "JobStatus",
    "QueueItem",
    "QueuedJob",
    "QueueSettings",
    "RetryPolicy",
    "TaskDefinition",
    # Exceptions
    "CancellationError",
    "DispatcherFullError",
    "DuplicateJobError",
    "JobNotFoundError",
    "QueueError",
    "QueueFullError",
    "ResourceLockedError",
    "WorkerNotRunningError",
    "WorkerTimeoutError",
]
