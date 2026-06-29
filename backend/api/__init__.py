"""
API Gateway Layer for Local Clip Studio.

Provides:
- FastAPI application factory and configuration
- HTTP route handlers organized by resource
- Middleware (CORS, request ID, error handling)
- Dependency injection providers
- WebSocket manager for real-time events

Communication boundary between the frontend (React SPA) and backend services.
"""
