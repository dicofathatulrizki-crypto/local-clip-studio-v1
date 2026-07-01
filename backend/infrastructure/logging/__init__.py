"""Logging infrastructure — package init."""

from backend.infrastructure.logging.logger import (
    configure_logging,
    get_logger,
    LoggerProtocol,
)
from backend.infrastructure.logging.correlation import (
    CorrelationIDMiddleware,
    get_current_correlation_id,
    set_correlation_id,
    CorrelationIDContext,
)

__all__ = [
    "configure_logging",
    "get_logger",
    "LoggerProtocol",
    "CorrelationIDMiddleware",
    "get_current_correlation_id",
    "set_correlation_id",
    "CorrelationIDContext",
]
