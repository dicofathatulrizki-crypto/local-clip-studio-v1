"""Tests for Celery app configuration."""

from __future__ import annotations

from backend.infrastructure.queue.celery_app import (
    _JOB_TYPE_ROUTING,
    celery_app,
    get_routing_for,
)


class TestCeleryAppConfig:
    """Verify Celery app configuration."""

    def test_app_name(self) -> None:
        assert celery_app.main == "localclip"

    def test_task_serializer(self) -> None:
        assert celery_app.conf.task_serializer == "json"

    def test_result_serializer(self) -> None:
        assert celery_app.conf.result_serializer == "json"

    def test_routing(self) -> None:
        routes = celery_app.conf.task_routes
        assert routes["video_import"]["queue"] == "video"
        assert routes["export"]["queue"] == "export"
        assert routes["cache_cleanup"]["queue"] == "maintenance"

    def test_all_15_job_types_have_routing(self) -> None:
        expected_jobs = {
            "video_import", "audio_extraction", "proxy_generation",
            "scene_detection", "whisperx_stt", "yolo_vision",
            "ocr", "llm_analysis", "clip_generation",
            "caption_generation", "translation", "export",
            "thumbnail_generation", "ai_model_download", "cache_cleanup",
        }
        assert set(_JOB_TYPE_ROUTING.keys()) == expected_jobs

    def test_get_routing_for_known(self) -> None:
        routing = get_routing_for("video_import")
        assert routing["queue"] == "video"
        assert routing["priority"] == 5

    def test_get_routing_for_unknown(self) -> None:
        routing = get_routing_for("unknown_type")
        assert routing["queue"] == "default"
        assert routing["priority"] == 5

    def test_priority_values(self) -> None:
        """Verify priority values for each job type."""
        assert _JOB_TYPE_ROUTING["video_import"]["priority"] == 5
        assert _JOB_TYPE_ROUTING["scene_detection"]["priority"] == 4
        assert _JOB_TYPE_ROUTING["llm_analysis"]["priority"] == 3
        assert _JOB_TYPE_ROUTING["export"]["priority"] == 2
        assert _JOB_TYPE_ROUTING["cache_cleanup"]["priority"] == 1
