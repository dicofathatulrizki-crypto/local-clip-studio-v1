"""Unit tests for PluginCache."""

from __future__ import annotations

import time

from backend.infrastructure.plugins.cache import PluginCache
from backend.infrastructure.plugins.types import PluginManifest


class TestPluginCache:
    """Test the PluginCache class."""

    def setup_method(self) -> None:
        self.cache = PluginCache(max_size=5, ttl_seconds=3600)

    def test_set_and_get(self) -> None:
        self.cache.set("plugin-a", "instance_a")
        result = self.cache.get("plugin-a")
        assert result == "instance_a"

    def test_get_missing(self) -> None:
        result = self.cache.get("nonexistent")
        assert result is None

    def test_remove(self) -> None:
        self.cache.set("plugin-a", "value")
        self.cache.remove("plugin-a")
        assert self.cache.get("plugin-a") is None

    def test_clear(self) -> None:
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.clear()
        assert self.cache.is_empty is True
        assert self.cache.size() == 0

    def test_exists(self) -> None:
        self.cache.set("existing", "value")
        assert self.cache.exists("existing") is True
        assert self.cache.exists("missing") is False

    def test_eviction_lru(self) -> None:
        small_cache = PluginCache(max_size=2)
        small_cache.set("a", 1)
        small_cache.set("b", 2)
        small_cache.get("a")  # Touch 'a'
        small_cache.set("c", 3)  # Should evict 'b' (least recently used)
        assert small_cache.exists("a") is True
        assert small_cache.exists("b") is False
        assert small_cache.exists("c") is True

    def test_ttl_expiry(self) -> None:
        short_cache = PluginCache(ttl_seconds=0)  # 0 TTL = immediate expiry
        short_cache.set("short-lived", "value")
        # Need to give time for TTL to expire
        time.sleep(0.01)
        assert short_cache.get("short-lived") is None
        assert short_cache.exists("short-lived") is False

    def test_manifest_caching(self) -> None:
        manifest = PluginManifest(id="manifested", version="1.0.0")
        self.cache.set("manifested", "instance", manifest=manifest)
        cached_manifest = self.cache.get_manifest("manifested")
        assert cached_manifest is not None
        assert cached_manifest.id == "manifested"
        assert cached_manifest.version == "1.0.0"

    def test_manifest_get_missing(self) -> None:
        assert self.cache.get_manifest("nonexistent") is None

    def test_size(self) -> None:
        assert self.cache.size() == 0
        self.cache.set("a", 1)
        assert self.cache.size() == 1
        self.cache.set("b", 2)
        assert self.cache.size() == 2

    def test_is_empty(self) -> None:
        assert self.cache.is_empty is True
        self.cache.set("a", 1)
        assert self.cache.is_empty is False

    def test_remove_nonexistent(self) -> None:
        # Should not raise
        self.cache.remove("nonexistent")

    def test_zero_ttl_no_expiry_without_time(self) -> None:
        # Even with 0 TTL, cache is still populated after set
        zero_cache = PluginCache(ttl_seconds=0)
        zero_cache.set("immediate", "value")
        # Get right away should return None because TTL=0 means expired immediately
        assert zero_cache.get("immediate") is None

    def test_set_overwrites_existing(self) -> None:
        self.cache.set("key", "old_value")
        self.cache.set("key", "new_value")
        assert self.cache.get("key") == "new_value"
