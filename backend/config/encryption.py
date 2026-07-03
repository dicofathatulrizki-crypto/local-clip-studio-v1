"""API key encryption using Fernet symmetric encryption."""

from __future__ import annotations

import base64
import os
import platform
import hashlib
from pathlib import Path
from typing import ClassVar

from cryptography.fernet import Fernet, InvalidToken


class EncryptionKeyManager:
    """Manages the encryption key for API key storage.

    The key is derived from a machine-specific identifier and stored
    in the application config directory.
    """

    _instance: ClassVar[EncryptionKeyManager | None] = None

    def __init__(self, config_dir: str | Path | None = None) -> None:
        self._config_dir = Path(config_dir) if config_dir else self._default_config_dir()
        self._key_path = self._config_dir / "key.der"
        self._key: bytes | None = None

    @staticmethod
    def _default_config_dir() -> Path:
        """Get the default config directory."""
        home = Path.home()
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        else:
            base = home
        return base / ".localclip" / "config"

    def _derive_machine_key(self) -> bytes:
        """Derive a machine-specific encryption key."""
        machine_id = platform.node() or "unknown"
        machine_id += os.name
        machine_id += str(hashlib.sha256(str(Path.home()).encode()).hexdigest())
        digest = hashlib.sha256(machine_id.encode("utf-8")).digest()
        return digest

    def _ensure_config_dir(self) -> None:
        """Ensure the config directory exists."""
        self._config_dir.mkdir(parents=True, exist_ok=True)

    def get_or_create_key(self) -> bytes:
        """Get existing key or create a new one."""
        if self._key is not None:
            return self._key

        self._ensure_config_dir()

        if self._key_path.exists():
            self._key = self._key_path.read_bytes()
        else:
            raw_key = self._derive_machine_key()
            self._key = raw_key
            self._key_path.write_bytes(raw_key)
            self._key_path.chmod(0o600)

        return self._key

    def get_key(self) -> bytes | None:
        """Get the encryption key if it exists."""
        if self._key is not None:
            return self._key
        if self._key_path.exists():
            self._key = self._key_path.read_bytes()
            return self._key
        return None

    def reset_key(self) -> None:
        """Reset the key (invalidates existing encrypted data)."""
        self._key = None
        if self._key_path.exists():
            self._key_path.unlink()

    @classmethod
    def get_instance(cls) -> EncryptionKeyManager:
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class APIKeyEncryption:
    """Encrypts and decrypts API keys using Fernet."""

    def __init__(self, key_manager: EncryptionKeyManager | None = None) -> None:
        self._key_manager = key_manager or EncryptionKeyManager.get_instance()
        self._fernet: Fernet | None = None

    def _get_fernet(self) -> Fernet:
        """Get or create the Fernet cipher from machine-derived key."""
        if self._fernet is None:
            import base64
            raw_key = self._key_manager.get_or_create_key()
            # Pad or truncate to 32 bytes, then base64-encode for Fernet
            key_bytes = raw_key[:32].ljust(32, b'\0')
            encoded_key = base64.urlsafe_b64encode(key_bytes)
            self._fernet = Fernet(encoded_key)
        return self._fernet

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string value."""
        fernet = self._get_fernet()
        token = fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a string value."""
        fernet = self._get_fernet()
        try:
            plaintext = fernet.decrypt(ciphertext.encode("utf-8"))
            return plaintext.decode("utf-8")
        except InvalidToken:
            raise ValueError("Failed to decrypt: invalid token or key mismatch")

    @staticmethod
    def is_encrypted(value: str) -> bool:
        """Check if a string looks like a Fernet-encrypted token.

        Validates the structure by base64-decoding the value and checking
        for the minimum Fernet token size (version + timestamp + IV +
        ciphertext + HMAC = 73+ bytes). This does NOT attempt to decrypt
        the value, so no key is required.
        """
        try:
            decoded = base64.urlsafe_b64decode(value.encode("utf-8"))
            # Fernet v0 token minimum: version(1) + timestamp(8) + IV(16)
            # + ciphertext(16, AES block) + HMAC(32) = 73 bytes
            return len(decoded) >= 73
        except Exception:
            return False
