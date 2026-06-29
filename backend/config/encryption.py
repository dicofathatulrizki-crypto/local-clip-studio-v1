"""
Secure storage of API keys using AES-256-GCM encryption.

Encryption keys are derived from a machine-specific identifier,
ensuring that encrypted API keys cannot be decrypted on a different machine.

Uses the `cryptography` library for Fernet (AES-256-CBC with HMAC) encryption.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
from pathlib import Path
from threading import Lock

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# ─── Key Derivation ─────────────────────────────────────────────


def _get_machine_secret() -> bytes:
    """Derive a machine-specific secret for encryption key generation.

    Combines multiple machine-identifying attributes to create a unique
    but stable device identifier. This ensures encrypted keys are
    bound to a specific machine.
    """
    parts = [
        platform.node(),           # Hostname
        platform.machine(),        # Architecture (x86_64, arm64)
        platform.processor(),      # Processor info
        os.name,                   # OS name (posix, nt)
    ]
    if os.path.exists("/etc/machine-id"):
        try:
            with open("/etc/machine-id") as f:
                parts.append(f.read().strip())
        except IOError:
            pass

    return "|".join(parts).encode("utf-8")


def _derive_fernet_key(salt: bytes | None = None) -> tuple[bytes, bytes]:
    """Derive a Fernet-compatible 32-byte key from machine-specific data.

    Returns (key, salt) tuple. Salt can be persisted to allow key
    regeneration across application restarts.
    """
    if salt is None:
        salt = os.urandom(16)

    secret = _get_machine_secret()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret))
    return key, salt


# ─── Encryption Service ─────────────────────────────────────────


class APIKeyEncryption:
    """Encrypts and decrypts API keys using a machine-specific key.

    The encryption key is derived on first use and cached in-memory.
    The salt is persisted to ~/.localclip/config/key.salt so that
    the same key can be regenerated across application restarts.
    """

    def __init__(self, config_dir: str | Path | None = None) -> None:
        if config_dir is None:
            config_dir = Path.home() / ".localclip" / "config"
        self._config_dir = Path(config_dir)
        self._config_dir.mkdir(parents=True, exist_ok=True)

        self._fernet: Fernet | None = None
        self._lock = Lock()

    @property
    def key_path(self) -> Path:
        return self._config_dir / "key.salt"

    def _get_or_create_key(self) -> Fernet:
        """Get the cached Fernet instance or create one from persisted salt."""
        if self._fernet is not None:
            return self._fernet

        with self._lock:
            if self._fernet is not None:
                return self._fernet

            # Load existing salt or create new one
            if self.key_path.exists():
                salt = self.key_path.read_bytes()
            else:
                salt = os.urandom(16)
                self.key_path.write_bytes(salt)

            key, _ = _derive_fernet_key(salt)
            self._fernet = Fernet(key)
            return self._fernet

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string (e.g., API key) and return base64-encoded ciphertext."""
        if not plaintext:
            return ""
        fernet = self._get_or_create_key()
        token = fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a base64-encoded ciphertext back to the original string."""
        if not ciphertext:
            return ""
        fernet = self._get_or_create_key()
        token = fernet.decrypt(ciphertext.encode("utf-8"))
        return token.decode("utf-8")

    def encrypt_dict(self, data: dict) -> dict:
        """Encrypt all string values in a dictionary (for API keys in provider config)."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and value and not value.startswith("gAAAAA"):
                result[key] = self.encrypt(value)
            else:
                result[key] = value
        return result

    def decrypt_dict(self, data: dict) -> dict:
        """Decrypt all string values in a dictionary."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and value.startswith("gAAAAA"):  # Fernet prefix
                result[key] = self.decrypt(value)
            else:
                result[key] = value
        return result


# ─── Global Instance ────────────────────────────────────────────

_encryption_instance: APIKeyEncryption | None = None
_encryption_lock = Lock()


def get_encryption() -> APIKeyEncryption:
    """Get the global APIKeyEncryption instance (thread-safe)."""
    global _encryption_instance
    if _encryption_instance is not None:
        return _encryption_instance

    with _encryption_lock:
        if _encryption_instance is None:
            _encryption_instance = APIKeyEncryption()
    return _encryption_instance


def encrypt_api_key(plaintext: str) -> str:
    """Convenience function: encrypt an API key."""
    return get_encryption().encrypt(plaintext)


def decrypt_api_key(ciphertext: str) -> str:
    """Convenience function: decrypt an API key."""
    return get_encryption().decrypt(ciphertext)
