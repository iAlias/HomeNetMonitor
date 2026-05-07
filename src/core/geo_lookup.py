"""IP geolocation via the ip-api.com batch endpoint."""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import requests

from src.core.data_store import DataStore
from src.utils.constants import (
    GEO_API_RATE_LIMIT,
    GEO_API_URL,
    GEO_BATCH_INTERVAL_SECONDS,
    PRIVATE_PREFIXES,
)

logger = logging.getLogger(__name__)


def _is_private(ip: str) -> bool:
    """Return True if *ip* belongs to a private/RFC1918 range.

    Args:
        ip: IPv4 or IPv6 address string.

    Returns:
        ``True`` if the address is private.
    """
    return any(ip.startswith(p) for p in PRIVATE_PREFIXES)


class GeoLookup:
    """Batch IP geolocation using the free ip-api.com API.

    Collects IPs seen since the last flush, then calls the batch endpoint
    once per ``batch_interval`` seconds.  Results are cached in SQLite.

    Args:
        data_store: Shared :class:`~src.core.data_store.DataStore` instance.
        batch_interval: Seconds between batch API calls.
        request_timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        data_store: DataStore,
        batch_interval: float = GEO_BATCH_INTERVAL_SECONDS,
        request_timeout: float = 5.0,
    ) -> None:
        """Initialise the geo lookup service."""
        self._store = data_store
        self._batch_interval = batch_interval
        self._request_timeout = request_timeout
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, ip: str) -> None:
        """Enqueue *ip* for geolocation in the next batch.

        Private addresses are silently ignored.  Already-cached IPs and
        IPs already in the pending set are also silently ignored.  The
        cache check is performed inside the lock so that a concurrent
        :meth:`_flush` call cannot drain the pending set between the check
        and the add.

        Args:
            ip: IP address to look up.
        """
        if _is_private(ip):
            return
        with self._lock:
            if ip in self._pending:
                return
            if self._store.get_geo_cached(ip) is not None:
                return
            self._pending.add(ip)

    def get(self, ip: str) -> Optional[dict]:
        """Return cached geolocation data for *ip*, or ``None``.

        Args:
            ip: IP address to query.

        Returns:
            Dict with ``country``, ``city``, ``isp`` keys, or ``None``.
        """
        return self._store.get_geo_cached(ip)

    def start(self) -> None:
        """Start the background batch-flush thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="geo-lookup", daemon=True
        )
        self._thread.start()
        logger.debug("GeoLookup background thread started")

    def stop(self) -> None:
        """Signal the background thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Background thread loop: flush batches at regular intervals."""
        while not self._stop_event.wait(timeout=self._batch_interval):
            self._flush()
        # Final flush on exit
        self._flush()

    def _flush(self) -> None:
        """Take the pending IP set and query ip-api.com in batches."""
        with self._lock:
            if not self._pending:
                return
            ips = list(self._pending)
            self._pending.clear()

        # Filter out already-cached entries that were queued twice
        ips = [ip for ip in ips if self._store.get_geo_cached(ip) is None]
        if not ips:
            return

        # Split into chunks of GEO_API_RATE_LIMIT
        for chunk_start in range(0, len(ips), GEO_API_RATE_LIMIT):
            chunk = ips[chunk_start : chunk_start + GEO_API_RATE_LIMIT]
            self._query_batch(chunk)

    def _query_batch(self, ips: list[str]) -> None:
        """Query ip-api.com for a list of IPs and store results.

        Args:
            ips: List of IP address strings (max 100).
        """
        payload = [{"query": ip, "fields": "query,country,city,isp,status"} for ip in ips]
        try:
            resp = requests.post(
                GEO_API_URL,
                json=payload,
                timeout=self._request_timeout,
            )
            resp.raise_for_status()
            results = resp.json()
        except requests.RequestException as exc:
            logger.warning("ip-api.com request failed: %s", exc)
            return
        except ValueError as exc:
            logger.warning("ip-api.com response parse error: %s", exc)
            return

        for item in results:
            if not isinstance(item, dict):
                continue
            if item.get("status") != "success":
                continue
            self._store.set_geo_cached(
                ip=item.get("query", ""),
                country=item.get("country", ""),
                city=item.get("city", ""),
                isp=item.get("isp", ""),
            )
        logger.debug("Geo batch: resolved %d IPs", len(results))
