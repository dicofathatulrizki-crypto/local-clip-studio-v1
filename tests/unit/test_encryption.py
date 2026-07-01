"""Tests for encryption module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.config.encryption import APIKeyEncryption, EncryptionKeyManager


class TestEncryptionKeyManager:
    """Test encryption key management."""

    def test_key_creation(self):
        """Test that a key is created if none exists."""
        with tempfile.TemporaryDirectory() as tmp:
            manager = EncryptionKeyManager(config_dir=tmp)
            key = manager.get_or_create_key()
            assert isinstance(key, bytes)
            assert len(key) > 0

    def test_key_persistence(self):
        """Test that the key persists across instances."""
        with tempfile.TemporaryDirectory() as tmp:
            manager1 = EncryptionKeyManager(config_dir=tmp)
            key1 = manager1.get_or_create_key()

            manager2 = EncryptionKeyManager(config_dir=tmp)
            key2 = manager2.get_or_create_key()
            assert key1 == key2

    def test_key_file_permissions(self):
        """Test that key file is created."""
        with tempfile.TemporaryDirectory() as tmp:
            manager = EncryptionKeyManager(config_dir=tmp)
            manager.get_or_create_key()
            key_path = Path(tmp) / "key.der"
            assert key_path.exists()


class TestAPIKeyEncryption:
    """Test API key encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypt then decrypt returns the original value."""
        with tempfile.TemporaryDirectory() as tmp:
            manager = EncryptionKeyManager(config_dir=tmp)
            crypto = APIKeyEncryption(key_manager=manager)
            original = "sk-test-api-key-12345"
            encrypted = crypto.encrypt(original)
            decrypted = crypto.decrypt(encrypted)
            assert decrypted == original
            assert encrypted != original

    def test_encrypt_empty_string(self):
        """Test encryption of empty string."""
        with tempfile.TemporaryDirectory() as tmp:
            manager = EncryptionKeyManager(config_dir=tmp)
            crypto = APIKeyEncryption(key_manager=manager)
            encrypted = crypto.encrypt("")
            decrypted = crypto.decrypt(encrypted)
            assert decrypted == ""

    def test_decrypt_invalid_token(self):
        """Test that decrypting an invalid token raises ValueError."""
        with tempfile.TemporaryDirectory() as tmp:
            manager = EncryptionKeyManager(config_dir=tmp)
            crypto = APIKeyEncryption(key_manager=manager)
            with pytest.raises(ValueError):
                crypto.decrypt("invalid-token")
