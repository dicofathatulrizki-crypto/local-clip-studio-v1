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
- Domain events raised for job lifecycle changes
"""

from __future__ import annotations

from backend.infrastructure.queue.cancellation import CancellationManager
from backend.infrastructure.queue.dispatcher import Dispatcher
from backend.infrastructure.queue.events import QueueEventBus
from backend.infrastructure.queue.exceptions import (
    JobCancellationError,
    JobNotFoundError,
    JobTimeoutError,
    QueueFullError,
    QueueError,
    ResourceLockError,
    WorkerBusyError,
)
from backend.infrastructure.queue.health import HealthMonitor
from backend.infrastructure.queue.metrics import MetricsCollector
from backend.infrastructure.queue.models import (
    JobPriority,
    JobRecord,
    JobStatus,
    QueuedJob,
    QueueSettings,
    RetryPolicy,
    TaskDefinition,
)
from backend.infrastructure.queue.priority import PriorityQueue
from backend.infrastructure.queue.progress import QueueProgressReporter
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
    "QueueEventBus",
    "QueueProgressReporter",
    "RetryManager",
    "Scheduler",
    "TaskRegistry",
    "WorkerPool",
    # Models
    "JobPriority",
    "JobRecord",
    "JobStatus",
    "QueuedJob",
    "QueueSettings",
    "RetryPolicy",
    "TaskDefinition",
    # Exceptions
    "JobCancellationError",
    "JobNotFoundError",
    "JobTimeoutError",
    "QueueError",
    "QueueFullError",
    "ResourceLockError",
    "WorkerBusyError",
]
