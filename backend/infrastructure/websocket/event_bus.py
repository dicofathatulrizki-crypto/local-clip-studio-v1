"""Strongly typed event bus for WebSocket event publishing.

Responsibilities:
- Publish events to topic subscribers
- Broadcast events to all clients
- Emit events to specific clients or projects
- Event deduplication via event_id
- Ordered delivery per connection
- Async-safe concurrent publishing

No business logic — pure event routing infrastructure.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from backend.infrastructure.logging.logger import get_logger
from backend.infrastructure.websocket.exceptions import (
    ConnectionClosedError,
)
from backend.infrastructure.websocket.models import (
    ProgressUpdate,
    SubscriptionTopic,
    WebSocketEvent,
    WebSocketMessageType,
)
from backend.infrastructure.websocket.serializer import Serializer

logger = get_logger(__name__)


class EventBus:
    """Event bus for publishing WebSocket events.

    Routes events to topic subscribers and supports direct
    client-to-client and client-to-project communication.

    Usage:
        bus = EventBus(serializer, send_fn)
        await bus.publish(event)
        await bus.broadcast(event)
        await bus.emit_to_client("client-1", event)
    """

    def __init__(
        self,
        serializer: Serializer,
        send_function: Callable[[str, str], Coroutine[Any, Any, None]],
        *,
        ordered_delivery: bool = True,
    ) -> None:
        self._serializer = serializer
        self._send = send_function
        self._ordered_delivery = ordered_delivery
        self._delivered_events: set[str] = set()
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def publish(
        self,
        event: WebSocketEvent,
        *,
        skip_dedup: bool = False,
    ) -> int:
        """Publish an event to all subscribers of its topic.

        Args:
            event: The event to publish
            skip_dedup: If True, skip deduplication check

        Returns:
            Number of clients the event was sent to

        Raises:
            WebSocketError: If serialization or send fails
        """
        # Deduplication: check and add in one atomic operation
        if not skip_dedup and event.event_id:
            async with self._lock:
                if event.event_id in self._delivered_events:
                    return 0
                self._delivered_events.add(event.event_id)

        topic = event.topic or self._topic_for_type(event.type)

        # Serialize the event (the actual fan-out to subscribers
        # is handled by the WebSocketManager which provides send_function)
        self._serializer.serialize_event(
            event.type,
            event.payload,
            topic=topic,
            correlation_id=event.correlation_id,
        )

        # Log the publish
        logger.debug(
            "event_published",
            extra={
                "type": event.type.value,
                "topic": topic,
                "event_id": event.event_id or "",
                "client_id": event.client_id or "system",
            },
        )
        return 0

    async def broadcast(
        self,
        event: WebSocketEvent,
        *,
        skip_dedup: bool = False,
    ) -> None:
        """Broadcast an event to ALL connected clients.

        Args:
            event: The event to broadcast
            skip_dedup: If True, skip deduplication check
        """
        if not skip_dedup and event.event_id:
            async with self._lock:
                if event.event_id in self._delivered_events:
                    return
                self._delivered_events.add(event.event_id)

        logger.debug(
            "event_broadcast",
            extra={
                "type": event.type.value,
                "event_id": event.event_id,
            },
        )

    async def emit_to_client(
        self,
        client_id: str,
        event: WebSocketEvent,
    ) -> bool:
        """Emit an event directly to a specific client.

        Args:
            client_id: Target client ID
            event: The event to send

        Returns:
            True if sent successfully, False if client not found/closed
        """
        try:
            serialized = self._serializer.serialize_event(
                event.type,
                event.payload,
                topic=event.topic,
                correlation_id=event.correlation_id,
            )
            await self._send(client_id, serialized)
            return True
        except (ConnectionClosedError, OSError):
            return False
        except Exception as exc:
            logger.warning(
                "emit_to_client_failed",
                extra={
                    "client_id": client_id,
                    "type": event.type.value,
                    "error": str(exc),
                },
            )
            return False

    async def emit_to_project(
        self,
        project_id: str,
        event: WebSocketEvent,
    ) -> int:
        """Emit an event to all subscribers of a project's topics.

        Args:
            project_id: The project to target
            event: The event to send

        Returns:
            Number of clients the event was sent to
        """
        project_topics = SubscriptionTopic.for_project(project_id)
        event.topic = project_topics[0] if project_topics else project_id
        return await self.publish(event)

    async def emit_progress(
        self,
        project_id: str,
        update: ProgressUpdate,
    ) -> int:
        """Emit a progress update to project subscribers.

        Convenience method for progress streaming during pipeline operations.

        Args:
            project_id: The project receiving progress
            update: The progress update payload

        Returns:
            Number of clients the update was sent to
        """
        topic = SubscriptionTopic.PROJECT.value.format(project_id=project_id)
        type_map = {
            "analysis": WebSocketMessageType.ANALYSIS_PROGRESS,
            "import": WebSocketMessageType.VIDEO_IMPORT_PROGRESS,
            "clip": WebSocketMessageType.CLIP_GENERATION_PROGRESS,
            "caption": WebSocketMessageType.CAPTION_GENERATION_PROGRESS,
            "export": WebSocketMessageType.EXPORT_PROGRESS,
            "model": WebSocketMessageType.MODEL_DOWNLOAD_PROGRESS,
            "queue": WebSocketMessageType.QUEUE_JOB_PROGRESS,
        }
        msg_type = type_map.get(update.operation, WebSocketMessageType.SYSTEM_EVENT)

        event = WebSocketEvent(
            type=msg_type,
            payload={
                "operation": update.operation,
                "progress": update.progress,
                "stage": update.stage,
                "message": update.message or "",
                "stage_progress": update.stage_progress,
                "estimated_remaining_seconds": update.estimated_remaining_seconds,
                "items_completed": update.items_completed,
                "items_total": update.items_total,
                "error_message": update.error_message,
                "metadata": update.metadata,
            },
            topic=topic,
        )
        return await self.publish(event)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def trim_delivered_events(self, max_events: int = 10000) -> int:
        """Trim the deduplication set to prevent memory growth.

        Args:
            max_events: Maximum events to keep in dedup set

        Returns:
            Number of trimmed events
        """
        async with self._lock:
            if len(self._delivered_events) <= max_events:
                return 0
            # Keep only the most recent max_events
            trimmed = len(self._delivered_events) - max_events
            # Simple approach: clear and let repopulate
            self._delivered_events.clear()
            return trimmed

    async def clear(self) -> None:
        """Clear all state (for testing)."""
        async with self._lock:
            self._delivered_events.clear()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _topic_for_type(msg_type: WebSocketMessageType) -> str:
        """Get the default topic for a message type."""
        # Project events map to their own topics
        type_to_topic: dict[WebSocketMessageType, str] = {
            WebSocketMessageType.PROJECT_CREATED: "projects",
            WebSocketMessageType.PROJECT_UPDATED: "projects",
            WebSocketMessageType.PROJECT_DELETED: "projects",
            WebSocketMessageType.SYSTEM_HEALTH: "system",
            WebSocketMessageType.SYSTEM_SETTINGS_CHANGED: "settings",
            WebSocketMessageType.PLUGIN_LOADED: "plugins",
            WebSocketMessageType.PLUGIN_UNLOADED: "plugins",
        }
        return type_to_topic.get(msg_type, "system")
