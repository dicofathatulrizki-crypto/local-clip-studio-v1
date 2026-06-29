"""
Infrastructure layer for Local Clip Studio.

Provides concrete implementations of domain interfaces:
- Database (SQLAlchemy repositories, Alembic migrations)
- FileSystem (directory management, file operations, cleanup)
- HAL (Hardware Abstraction Layer for GPU backends)
- FFmpeg (video processing subprocess management)
- Queue (Celery background job processing)
- WebSocket (real-time event streaming)
- Plugins (discovery, loading, interface definitions)
- Logging (structured JSON logging, correlation)
"""
