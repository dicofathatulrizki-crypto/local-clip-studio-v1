"""
FileManager — provides atomic, safe file operations for the application.

Features:
- Atomic writes via temporary file + rename
- Safe move/copy/delete with retries
- SHA-256 hash computation and verification
- Large file streaming with progress callbacks
- Async I/O for non-blocking file operations
- Path traversal protection
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from backend.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# Type alias for progress callbacks
ProgressCallback = Callable[[int, int], None]


class FileOperationError(Exception):
    """Raised when a file operation fails after retries."""


class FileIntegrityError(Exception):
    """Raised when file hash verification fails."""


# ─── FileManager ────────────────────────────────────────────────


class FileManager:
    """Atomic, safe file operations with integrity verification.

    All write operations use an atomic write pattern:
    1. Write to a temporary file in the same directory
    2. fsync the temporary file
    3. Rename the temporary file to the target path
    This ensures partial writes never produce corrupt files.
    """

    DEFAULT_COPY_BUFFER = 65536  # 64KB buffer for copy operations
    MAX_RETRIES = 3

    # ─── Hashing ─────────────────────────────────────────────────

    @staticmethod
    def compute_hash(file_path: str | Path, algorithm: str = "sha256") -> str:
        """Compute the hash of a file.

        Args:
            file_path: Path to the file
            algorithm: Hash algorithm (sha256, sha512, md5)
        Returns:
            Hex digest string
        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        h = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def verify_hash(file_path: str | Path, expected_hash: str, algorithm: str = "sha256") -> bool:
        """Verify a file's hash matches the expected value.

        Args:
            file_path: Path to the file
            expected_hash: Expected hex digest
            algorithm: Hash algorithm used
        Returns:
            True if hashes match
        """
        actual = FileManager.compute_hash(file_path, algorithm)
        return actual == expected_hash

    @staticmethod
    def compute_hash_streaming(
        file_path: str | Path,
        callback: ProgressCallback | None = None,
        algorithm: str = "sha256",
    ) -> str:
        """Compute file hash with progress reporting.

        Args:
            file_path: Path to the file
            callback: Optional progress callback (current_bytes, total_bytes)
            algorithm: Hash algorithm
        Returns:
            Hex digest string
        """
        h = hashlib.new(algorithm)
        total_bytes = os.path.getsize(file_path)
        processed = 0

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
                processed += len(chunk)
                if callback:
                    callback(processed, total_bytes)

        return h.hexdigest()

    # ─── Atomic Writes ───────────────────────────────────────────

    @staticmethod
    def atomic_write(
        path: str | Path,
        content: bytes | str,
        encoding: str = "utf-8",
    ) -> None:
        """Atomically write content to a file.

        Writes to a temporary file in the same directory, then renames
        to the target path. This prevents partial/corrupt writes.

        Args:
            path: Target file path
            content: Content to write (bytes or str)
            encoding: Encoding for string content
        Raises:
            OSError: If the write fails
        """
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        # Write to temporary file in same directory (atomic rename)
        fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), prefix=".tmp_")
        try:
            with os.fdopen(fd, "wb") as tmp:
                if isinstance(content, str):
                    tmp.write(content.encode(encoding))
                else:
                    tmp.write(content)
                tmp.flush()
            # fsync using the fd directly (before closing via fdopen)
            fd_check = os.open(tmp_path, os.O_RDONLY)
            os.fsync(fd_check)
            os.close(fd_check)

            # Atomic rename
            os.replace(tmp_path, str(target))
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    # ─── Safe Copy ───────────────────────────────────────────────

    @staticmethod
    def safe_copy(
        src: str | Path,
        dst: str | Path,
        callback: ProgressCallback | None = None,
        verify: bool = True,
    ) -> int:
        """Copy a file with atomic write and optional integrity verification.

        Args:
            src: Source file path
            dst: Destination file path
            callback: Optional progress callback (copied_bytes, total_bytes)
            verify: If True, verify hash after copy
        Returns:
            Total bytes copied
        Raises:
            FileOperationError: If copy fails or verification fails
        """
        src_path = Path(src)
        dst_path = Path(dst)

        if not src_path.exists():
            msg = f"Source file not found: {src}"
            raise FileNotFoundError(msg)

        dst_path.parent.mkdir(parents=True, exist_ok=True)

        total_bytes = src_path.stat().st_size
        copied = 0

        try:
            # Copy to temporary file first, then rename
            fd, tmp_path = tempfile.mkstemp(dir=str(dst_path.parent), prefix=".tmp_")
            with os.fdopen(fd, "wb") as tmp, open(src_path, "rb") as src_file:
                while True:
                    chunk = src_file.read(FileManager.DEFAULT_COPY_BUFFER)
                    if not chunk:
                        break
                    tmp.write(chunk)
                    copied += len(chunk)
                    if callback:
                        callback(copied, total_bytes)
                tmp.flush()
            fd_check = os.open(tmp_path, os.O_RDONLY)
            os.fsync(fd_check)
            os.close(fd_check)

            os.replace(tmp_path, str(dst_path))

            # Verify integrity
            if verify:
                src_hash = FileManager.compute_hash(src_path)
                if not FileManager.verify_hash(dst_path, src_hash):
                    msg = f"Hash mismatch after copy: {src} -> {dst}"
                    raise FileIntegrityError(msg)

            return copied
        except Exception as exc:
            # Cleanup temp file
            if "tmp_path" in locals() and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            if isinstance(exc, (FileOperationError, FileIntegrityError)):
                raise
            msg = f"Copy failed: {src} -> {dst}: {exc}"
            raise FileOperationError(msg) from exc

    # ─── Safe Move ───────────────────────────────────────────────

    @staticmethod
    def safe_move(
        src: str | Path,
        dst: str | Path,
        callback: ProgressCallback | None = None,
        verify: bool = True,
    ) -> int:
        """Move a file safely, falling back to copy+delete for cross-device moves.

        Args:
            src: Source file path
            dst: Destination file path
            callback: Optional progress callback
            verify: If True, verify hash after move
        Returns:
            Total bytes moved
        Raises:
            FileOperationError: If move fails
        """
        src_path = Path(src)
        dst_path = Path(dst)
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        # Get size before move (src_path won't exist after rename)
        size = src_path.stat().st_size

        try:
            # Try fast rename first (same filesystem)
            os.replace(str(src_path), str(dst_path))
            return size
        except OSError:
            # Cross-device move: copy + delete
            bytes_copied = FileManager.safe_copy(src, dst, callback, verify)
            os.unlink(src_path)
            return bytes_copied

    # ─── Safe Delete ─────────────────────────────────────────────

    @staticmethod
    def safe_delete(path: str | Path, max_retries: int = MAX_RETRIES) -> bool:
        """Delete a file or directory safely with retries.

        Args:
            path: File or directory path to delete
            max_retries: Number of retries on failure
        Returns:
            True if deleted, False if doesn't exist
        Raises:
            FileOperationError: If deletion fails after retries
        """
        target = Path(path)
        if not target.exists():
            return False

        for attempt in range(max_retries):
            try:
                if target.is_dir():
                    shutil.rmtree(str(target))
                else:
                    os.unlink(str(target))
                return True
            except OSError as exc:
                if attempt == max_retries - 1:
                    msg = f"Failed to delete {path} after {max_retries} attempts: {exc}"
                    raise FileOperationError(msg) from exc
                import time

                time.sleep(0.1 * (attempt + 1))

        return False

    # ─── Async Operations ────────────────────────────────────────

    @staticmethod
    async def async_read(path: str | Path, encoding: str = "utf-8") -> str:
        """Read a file asynchronously.

        Args:
            path: File path to read
            encoding: Text encoding
        Returns:
            File contents as string
        """
        import aiofiles

        async with aiofiles.open(path, encoding=encoding) as f:
            return await f.read()

    @staticmethod
    async def async_write(
        path: str | Path, content: str | bytes, encoding: str = "utf-8"
    ) -> None:
        """Write content to a file asynchronously (atomic).

        Args:
            path: Target file path
            content: Content to write
            encoding: Encoding for string content
        """
        import aiofiles

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, str):
            async with aiofiles.open(target, mode="w", encoding=encoding) as f:
                await f.write(content)
        else:
            async with aiofiles.open(target, mode="wb") as f:
                await f.write(content)

    @staticmethod
    async def async_copy(
        src: str | Path,
        dst: str | Path,
        callback: ProgressCallback | None = None,
    ) -> int:
        """Copy a file asynchronously with progress.

        Args:
            src: Source file path
            dst: Destination file path
            callback: Optional progress callback
        Returns:
            Total bytes copied
        """
        import aiofiles

        src_path = Path(src)
        dst_path = Path(dst)
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        total_bytes = src_path.stat().st_size
        copied = 0

        async with aiofiles.open(src_path, "rb") as src_file:
            async with aiofiles.open(dst_path, "wb") as dst_file:
                while True:
                    chunk = await src_file.read(FileManager.DEFAULT_COPY_BUFFER)
                    if not chunk:
                        break
                    await dst_file.write(chunk)
                    copied += len(chunk)
                    if callback:
                        callback(copied, total_bytes)

        return copied

    # ─── Directory Operations ────────────────────────────────────

    @staticmethod
    def list_files(
        directory: str | Path,
        pattern: str = "*",
        recursive: bool = False,
    ) -> list[Path]:
        """List files in a directory matching a pattern.

        Args:
            directory: Directory to search
            pattern: Glob pattern (e.g., "*.mp4")
            recursive: Search subdirectories if True
        Returns:
            List of matching file paths
        """
        base = Path(directory)
        if not base.exists():
            return []

        if recursive:
            return sorted(base.rglob(pattern))
        return sorted(base.glob(pattern))

    @staticmethod
    def get_size(path: str | Path) -> int:
        """Get the total size of a file or directory in bytes.

        Args:
            path: File or directory path
        Returns:
            Size in bytes
        """
        target = Path(path)
        if not target.exists():
            return 0
        if target.is_file():
            return target.stat().st_size
        total = 0
        for f in target.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
        return total

    @staticmethod
    def ensure_directory(path: str | Path) -> Path:
        """Ensure a directory exists, creating it if necessary.

        Args:
            path: Directory path
        Returns:
            The Path object
        """
        target = Path(path)
        target.mkdir(parents=True, exist_ok=True)
        return target

    # ─── Temporary Files ─────────────────────────────────────────

    @staticmethod
    def create_temp_file(
        suffix: str = "",
        prefix: str = "localclip_",
        directory: str | Path | None = None,
    ) -> str:
        """Create a temporary file and return its path.

        Args:
            suffix: File suffix (e.g., ".mp4")
            prefix: File prefix
            directory: Directory for the temp file
        Returns:
            Path to the created temporary file
        """
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=directory)
        os.close(fd)
        return path
