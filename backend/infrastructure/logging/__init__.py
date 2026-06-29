"""
Structured JSON logging for Local Clip Studio.

Provides:
- JSON-formatted log output for machine parsing
- Correlation ID propagation through async contexts
- Log rotation with configurable size and retention
- Sensitive data filtering (API keys never logged)
- Per-module log level configuration
"""
from __future__ import annotations
