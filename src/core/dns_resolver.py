"""Reverse DNS resolver with in-process cache and thread-pool execution."""
from __future__ import annotations

import logging
import socket
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Optional

from src.utils.constants import DNS_CACHE_TTL_SECONDS, DNS_LOOKUP_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class DnsResolver:
    """Asynchronous reverse-DNS resolver backed by a thread pool.

    Results are cached in a dict to avoid repeated lookups.  The cache
    never exceeds ``max_cache_size`` entries (oldest entries are evicted
    when the limit is reached).  All cache accesses are protected by an
    internal :class:`threading.Lock` so the resolver is safe to use from
    multiple threads simultaneously.

    Args:
        max_workers: Number of threads in the pool.
        timeout: Per-lookup timeout in seconds.
        max_cache_size: Maximum number of cache entries.
    """

    def __init__(
        self,
        max_workers: int = 8,
        timeout: float = DNS_LOOKUP_TIMEOUT_SECONDS,
        max_cache_size: int = 4096,
    ) -> None:
        """Initialise the resolver."""
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="dns")
        self._cache: dict[str, str] = {}
        self._cache_lock = threading.Lock()
        self._timeout = timeout
        self._max_cache_size = max_cache_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, ip: str) -> str:
        """Return a hostname for *ip*, using the cache when possible.

        Blocks for up to ``timeout`` seconds.  On timeout or any error,
        the raw IP string is returned and cached.

        Args:
            ip: IPv4 or IPv6 address string.

        Returns:
            Resolved hostname, or *ip* itself if resolution fails.
        """
        with self._cache_lock:
            if ip in self._cache:
                return self._cache[ip]

        hostname = self._do_lookup(ip)
        self._store(ip, hostname)
        return hostname

    def resolve_async(self, ip: str, callback) -> None:
        """Submit a background DNS lookup and call *callback(ip, hostname)*.

        If *ip* is already cached the callback is called synchronously with
        the cached value.

        Note: if the cache entry for *ip* is invalidated between the cache
        check and the callback invocation, the callback will still receive
        the value that was cached at lookup time.  This is intentional —
        callers should treat the hostname as a best-effort hint.

        Args:
            ip: IPv4 or IPv6 address string.
            callback: Callable ``(ip: str, hostname: str) -> None``.
        """
        with self._cache_lock:
            cached = self._cache.get(ip)

        if cached is not None:
            callback(ip, cached)
            return

        def _task() -> None:
            hostname = self._do_lookup(ip)
            self._store(ip, hostname)
            try:
                callback(ip, hostname)
            except Exception as exc:  # noqa: BLE001
                logger.debug("DNS callback error for %s: %s", ip, exc)

        self._executor.submit(_task)

    def get_cached(self, ip: str) -> Optional[str]:
        """Return the cached hostname for *ip*, or ``None`` if not cached.

        Args:
            ip: IP address to query.

        Returns:
            Cached hostname or ``None``.
        """
        with self._cache_lock:
            return self._cache.get(ip)

    def invalidate(self, ip: str) -> None:
        """Remove *ip* from the cache.

        Args:
            ip: IP address to remove.
        """
        with self._cache_lock:
            self._cache.pop(ip, None)

    def shutdown(self) -> None:
        """Shut down the thread pool, waiting for pending lookups."""
        self._executor.shutdown(wait=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _do_lookup(self, ip: str) -> str:
        """Perform the blocking reverse-DNS call in the current thread.

        Args:
            ip: IP address to look up.

        Returns:
            Hostname string, or *ip* on failure.
        """
        future = self._executor.submit(self._getnameinfo, ip)
        try:
            return future.result(timeout=self._timeout)
        except FuturesTimeout:
            logger.debug("DNS timeout for %s", ip)
            future.cancel()
            return ip
        except Exception as exc:  # noqa: BLE001
            logger.debug("DNS error for %s: %s", ip, exc)
            return ip

    @staticmethod
    def _getnameinfo(ip: str) -> str:
        """Blocking wrapper around ``socket.getnameinfo``.

        Args:
            ip: IP address to resolve.

        Returns:
            Hostname string.
        """
        host, _ = socket.getnameinfo((ip, 0), socket.NI_NAMEREQD)
        return host

    def _store(self, ip: str, hostname: str) -> None:
        """Store a resolved hostname and evict oldest if over capacity.

        Args:
            ip: IP address key.
            hostname: Hostname value.
        """
        with self._cache_lock:
            if len(self._cache) >= self._max_cache_size:
                # Evict the oldest entry (first inserted key in CPython 3.7+)
                try:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                except StopIteration:
                    pass
            self._cache[ip] = hostname
