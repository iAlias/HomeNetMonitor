"""Unit tests for DnsResolver."""
from __future__ import annotations

import socket
import threading
import time
from concurrent.futures import Future
from unittest.mock import MagicMock, patch

import pytest

from src.core.dns_resolver import DnsResolver


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDnsResolver:
    """Tests for DnsResolver cache and lookup behaviour."""

    def setup_method(self) -> None:
        """Create a fresh DnsResolver for each test."""
        self.resolver = DnsResolver(max_workers=2, timeout=1.0, max_cache_size=5)

    def teardown_method(self) -> None:
        """Shut down the thread pool."""
        self.resolver.shutdown()

    # ------------------------------------------------------------------
    # Cache behaviour
    # ------------------------------------------------------------------

    def test_cache_hit_returns_without_lookup(self) -> None:
        """resolve() should return the cached value without calling socket."""
        self.resolver._cache["1.1.1.1"] = "one.one.one.one"
        with patch("socket.getnameinfo") as mock_gni:
            result = self.resolver.resolve("1.1.1.1")
        mock_gni.assert_not_called()
        assert result == "one.one.one.one"

    def test_get_cached_returns_none_for_unknown(self) -> None:
        """get_cached() should return None when the IP is not in the cache."""
        assert self.resolver.get_cached("9.9.9.9") is None

    def test_get_cached_returns_value_after_resolve(self) -> None:
        """get_cached() should return the hostname after a successful resolve."""
        with patch.object(
            self.resolver, "_do_lookup", return_value="example.com"
        ):
            self.resolver.resolve("93.184.216.34")

        assert self.resolver.get_cached("93.184.216.34") == "example.com"

    def test_invalidate_removes_cache_entry(self) -> None:
        """invalidate() should remove the entry from the cache."""
        self.resolver._cache["1.2.3.4"] = "host.example.com"
        self.resolver.invalidate("1.2.3.4")
        assert self.resolver.get_cached("1.2.3.4") is None

    def test_cache_eviction_at_max_size(self) -> None:
        """When the cache is full the oldest entry should be evicted."""
        for i in range(5):
            self.resolver._cache[f"10.0.0.{i}"] = f"host{i}.local"

        # Adding a 6th entry should evict 10.0.0.0
        self.resolver._store("10.0.0.5", "host5.local")
        assert len(self.resolver._cache) == 5
        assert "10.0.0.0" not in self.resolver._cache
        assert "10.0.0.5" in self.resolver._cache

    # ------------------------------------------------------------------
    # Successful lookup
    # ------------------------------------------------------------------

    def test_successful_lookup_cached_and_returned(self) -> None:
        """A successful socket lookup should be cached and returned."""
        with patch.object(
            DnsResolver, "_getnameinfo", return_value="dns.google"
        ):
            result = self.resolver.resolve("8.8.8.8")

        assert result == "dns.google"
        assert self.resolver.get_cached("8.8.8.8") == "dns.google"

    # ------------------------------------------------------------------
    # Timeout handling
    # ------------------------------------------------------------------

    def test_timeout_returns_raw_ip(self) -> None:
        """When lookup exceeds timeout the raw IP should be returned."""
        def _slow_lookup(_ip: str) -> str:
            time.sleep(5)
            return "should-not-reach"

        with patch.object(DnsResolver, "_getnameinfo", side_effect=_slow_lookup):
            resolver = DnsResolver(max_workers=1, timeout=0.1)
            result = resolver.resolve("123.45.67.89")
            resolver.shutdown()

        # Should fall back to the raw IP
        assert result == "123.45.67.89"

    def test_socket_error_returns_raw_ip(self) -> None:
        """A socket.herror during lookup should return the raw IP."""
        with patch.object(
            DnsResolver,
            "_getnameinfo",
            side_effect=socket.herror("name not found"),
        ):
            result = self.resolver.resolve("1.2.3.4")

        assert result == "1.2.3.4"
        assert self.resolver.get_cached("1.2.3.4") == "1.2.3.4"

    # ------------------------------------------------------------------
    # Async resolve
    # ------------------------------------------------------------------

    def test_resolve_async_calls_callback(self) -> None:
        """resolve_async() should call the callback with (ip, hostname)."""
        received: list[tuple[str, str]] = []
        done = threading.Event()

        def callback(ip: str, hostname: str) -> None:
            received.append((ip, hostname))
            done.set()

        with patch.object(DnsResolver, "_getnameinfo", return_value="async.host"):
            self.resolver.resolve_async("5.6.7.8", callback)

        done.wait(timeout=3)
        assert len(received) == 1
        assert received[0] == ("5.6.7.8", "async.host")

    def test_resolve_async_cached_calls_sync(self) -> None:
        """resolve_async() should call callback synchronously if IP is cached."""
        self.resolver._cache["4.3.2.1"] = "cached.host"
        received: list[tuple[str, str]] = []

        def callback(ip: str, hostname: str) -> None:
            received.append((ip, hostname))

        with patch("socket.getnameinfo") as mock_gni:
            self.resolver.resolve_async("4.3.2.1", callback)

        mock_gni.assert_not_called()
        assert received == [("4.3.2.1", "cached.host")]
