"""
ModelStorageManager — manages AI model files on disk.

Models are stored under ~/.localclip/models/ with subdirectories
for each model type (whisper, yolo, sam, llm, embeddings).
Handles download tracking, integrity verification via checksums,
and provides storage usage reporting.
"""
from __future__ import annotations

from pathlib import Path

from backend.config.settings import get_settings
from backend.infrastructure.filesystem.file_manager import FileManager
from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ModelStorageManager:
    """Manages AI model file storage, integrity, and lifecycle.

    Model categories and their subdirectories:
    - whisper/  : Whisper/WhisperX model files
    - yolo/     : YOLOv8 weights
    - sam/      : SAM model weights
    - llm/      : Local LLM GGUF files
    - embeddings/: Embedding model files
    """

    MODEL_CATEGORIES = ("whisper", "yolo", "sam", "llm", "embeddings")

    def __init__(self, base_path: str | Path | None = None) -> None:
        if base_path:
            self._base = Path(base_path)
        else:
            settings = get_settings()
            self._base = Path(settings.app_directory)

    @property
    def models_dir(self) -> Path:
        """Get the models root directory."""
        return self._base / "models"

    def category_dir(self, category: str) -> Path:
        """Get the directory for a model category.

        Args:
            category: Model category (whisper, yolo, sam, llm, embeddings)
        Returns:
            Path to the category directory
        Raises:
            ValueError: If category is unknown
        """
        if category not in self.MODEL_CATEGORIES:
            msg = f"Unknown model category: {category}. Valid: {self.MODEL_CATEGORIES}"
            raise ValueError(msg)
        return self.models_dir / category

    def ensure_dirs(self) -> None:
        """Create all model category directories."""
        self.models_dir.mkdir(parents=True, exist_ok=True)
        for category in self.MODEL_CATEGORIES:
            (self.models_dir / category).mkdir(parents=True, exist_ok=True)

    def model_path(self, category: str, model_id: str, filename: str = "") -> Path:
        """Get the path for a specific model file.

        Args:
            category: Model category
            model_id: Model identifier (e.g., "large-v3", "yolov8n-face")
            filename: Optional specific filename within the model directory
        Returns:
            Path to the model
        """
        cat_dir = self.category_dir(category)
        model_dir = cat_dir / model_id
        if filename:
            return model_dir / filename
        return model_dir

    def list_models(self, category: str | None = None) -> list[dict[str, object]]:
        """List all stored models, optionally filtered by category.

        Args:
            category: Optional category filter
        Returns:
            List of dicts with model metadata
        """
        models: list[dict[str, object]] = []
        categories = [category] if category else self.MODEL_CATEGORIES

        for cat in categories:
            cat_dir = self.category_dir(cat)
            if not cat_dir.exists():
                continue
            for item in cat_dir.iterdir():
                if item.is_dir():
                    size = FileManager.get_size(item)
                    models.append({
                        "category": cat,
                        "model_id": item.name,
                        "path": str(item),
                        "size_bytes": size,
                        "size_gb": round(size / (1024**3), 2),
                    })

        return models

    def get_model_size(self, category: str, model_id: str) -> int:
        """Get the total size of a stored model in bytes.

        Args:
            category: Model category
            model_id: Model identifier
        Returns:
            Size in bytes
        """
        path = self.model_path(category, model_id)
        return FileManager.get_size(path)

    def verify_integrity(
        self, category: str, model_id: str, expected_hash: str, algorithm: str = "sha256"
    ) -> bool:
        """Verify the integrity of a stored model file.

        Scans all files in the model directory and checks the hash
        of the primary model file.

        Args:
            category: Model category
            model_id: Model identifier
            expected_hash: Expected SHA-256 hash
            algorithm: Hash algorithm
        Returns:
            True if hash matches
        """
        model_dir = self.models_dir / category / model_id
        if not model_dir.exists():
            return False

        # Find the largest file (likely the model weights)
        files = [f for f in model_dir.iterdir() if f.is_file()]
        if not files:
            return False

        primary = max(files, key=lambda f: f.stat().st_size)
        actual = FileManager.compute_hash(primary, algorithm)
        return actual == expected_hash

    def delete_model(self, category: str, model_id: str) -> bool:
        """Delete a stored model.

        Args:
            category: Model category
            model_id: Model identifier
        Returns:
            True if deleted
        """
        model_dir = self.model_path(category, model_id)
        if not model_dir.exists():
            return False

        result = FileManager.safe_delete(model_dir)
        if result:
            logger.info(
                "Deleted model",
                extra={"category": category, "model_id": model_id},
            )
        return result

    def get_usage(self) -> dict[str, object]:
        """Get model storage usage across all categories.

        Returns:
            Dict with per-category and total usage
        """
        categories = {}
        total_size = 0
        total_count = 0

        for cat in self.MODEL_CATEGORIES:
            cat_dir = self.category_dir(cat)
            size = FileManager.get_size(cat_dir)
            files = len(list(cat_dir.rglob("*"))) if cat_dir.exists() else 0
            categories[cat] = {"size_bytes": size, "file_count": files}
            total_size += size
            total_count += files

        return {
            "categories": categories,
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / (1024**3), 2),
            "total_file_count": total_count,
        }
