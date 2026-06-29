"""
Tests for the encryption system (backend/config/encryption.py).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.config.encryption import (
    APIKeyEncryption,
    decrypt_api_key,
    encrypt_api_key,
    get_encryption,
)


class TestAPIKeyEncryption:
    """Test API key encryption and decryption."""

    def test_encrypt_decrypt_roundtrip(self, temp_dir: Path) -> None:
        """Encrypting then decrypting should return the original value."""
        encryption = APIKeyEncryption(config_dir=temp_dir)
        original = "sk-test-api-key-12345"
        encrypted = encryption.encrypt(original)
        assert encrypted != original
        assert encrypted.startswith("gAAAAA")  # Fernet prefix

        decrypted = encryption.decrypt(encrypted)
        assert decrypted == original

    def test_empty_string(self, temp_dir: Path) -> None:
        """Empty string should return empty string (no-op)."""
        encryption = APIKeyEncryption(config_dir=temp_dir)
        assert encryption.encrypt("") == ""
        assert encryption.decrypt("") == ""

    def test_key_persistence(self, temp_dir: Path) -> None:
        """The salt file should be created and reused."""
        encryption1 = APIKeyEncryption(config_dir=temp_dir)
        original = "sk-test-key-abc"
        encrypted = encryption1.encrypt(original)

        # Create new instance pointing to same directory
        encryption2 = APIKeyEncryption(config_dir=temp_dir)
        decrypted = encryption2.decrypt(encrypted)
        assert decrypted == original

    def test_salt_file_created(self, temp_dir: Path) -> None:
        """Salt file should be created in the config directory."""
        encryption = APIKeyEncryption(config_dir=temp_dir)
        encryption.encrypt("test-key")
        assert (temp_dir / "key.salt").exists()

    def test_different_instances_same_key(self, temp_dir: Path) -> None:
        """Multiple instances with same config dir should be interchangeable."""
        enc1 = APIKeyEncryption(config_dir=temp_dir)
        enc2 = APIKeyEncryption(config_dir=temp_dir)

        encrypted = enc1.encrypt("cross-instance-test")
        decrypted = enc2.decrypt(encrypted)
        assert decrypted == "cross-instance-test"

    def test_encrypt_dict(self, temp_dir: Path) -> None:
        """encrypt_dict should encrypt string values only."""
        encryption = APIKeyEncryption(config_dir=temp_dir)
        data = {
            "api_key": "sk-secret-123",
            "model": "gpt-4",
            "temperature": 0.7,
            "enabled": True,
        }
        result = encryption.encrypt_dict(data)
        assert result["api_key"].startswith("gAAAAA")
        assert result["model"] == "gpt-4"
        assert result["temperature"] == 0.7
        assert result["enabled"] is True

    def test_decrypt_dict(self, temp_dir: Path) -> None:
        """decrypt_dict should decrypt Fernet-encrypted values."""
        encryption = APIKeyEncryption(config_dir=temp_dir)
        encrypted_key = encryption.encrypt("my-secret-key")
        data = {
            "api_key": encrypted_key,
            "model": "gpt-4",
        }
        result = encryption.decrypt_dict(data)
        assert result["api_key"] == "my-secret-key"
        assert result["model"] == "gpt-4"

    def test_encrypt_idempotent_different_ciphertext(self, temp_dir: Path) -> None:
        """Same plaintext should produce different ciphertext each time (random IV)."""
        encryption = APIKeyEncryption(config_dir=temp_dir)
        plaintext = "same-value"
        e1 = encryption.encrypt(plaintext)
        e2 = encryption.encrypt(plaintext)
        assert e1 != e2  # Different due to random IV
        assert encryption.decrypt(e1) == encryption.decrypt(e2)


class TestGlobalEncryption:
    """Test the global encryption instance functions."""

    def test_global_encrypt_decrypt(self) -> None:
        """Global encrypt_api_key and decrypt_api_key should work."""
        original = "sk-global-test-key"
        encrypted = encrypt_api_key(original)
        assert encrypted != original

        decrypted = decrypt_api_key(encrypted)
        assert decrypted == original

    def test_get_encryption_singleton(self) -> None:
        """get_encryption() should return the same instance."""
        e1 = get_encryption()
        e2 = get_encryption()
        assert e1 is e2
