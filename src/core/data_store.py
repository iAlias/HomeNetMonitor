"""In-memory and SQLite persistence for HomeNetMonitor sessions."""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.models.connection import Connection
from src.models.device import Device
from src.utils.constants import APPDATA_DIR, DB_PATH, DB_RETENTION_DAYS, MAX_CONNECTIONS_MEMORY

logger = logging.getLogger(__name__)


class DataStore:
    """Central data store combining in-memory state with SQLite persistence.

    Thread-safety: public methods acquire ``_lock`` before mutating state.

    Args:
        db_path: Path to the SQLite database file.  Created (with parent
            dirs) automatically if it does not exist.
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        """Initialise the data store and open the database connection."""
        self._db_path = db_path
        self._lock = threading.Lock()

        # In-memory state ------------------------------------------------
        self._devices: dict[str, Device] = {}          # keyed by MAC
        self._connections: dict[tuple, Connection] = {}  # keyed by flow_key
        self._alert_rules: list[dict] = []
        self._alert_log: list[dict] = []
        self._bandwidth_in: list[tuple[float, int]] = []   # (ts, bytes)
        self._bandwidth_out: list[tuple[float, int]] = []  # (ts, bytes)
        self._pending_connections: list[Connection] = []

        # SQLite ---------------------------------------------------------
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection = sqlite3.connect(
            str(db_path), check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

        # Load persisted rules from DB
        self._load_alert_rules()
        logger.info("DataStore initialised at %s", db_path)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        """Create all required tables if they don't exist."""
        sql = """
        CREATE TABLE IF NOT EXISTS devices (
            mac         TEXT PRIMARY KEY,
            ip          TEXT,
            hostname    TEXT,
            vendor      TEXT,
            status      TEXT,
            first_seen  TEXT,
            last_seen   TEXT
        );
        CREATE TABLE IF NOT EXISTS connections_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            src_ip          TEXT,
            dst_ip          TEXT,
            dst_host        TEXT,
            port            INTEGER,
            protocol        TEXT,
            service         TEXT,
            bytes           INTEGER,
            country         TEXT,
            city            TEXT,
            isp             TEXT,
            first_seen      TEXT,
            last_seen       TEXT,
            flagged         INTEGER
        );
        CREATE TABLE IF NOT EXISTS alerts_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT,
            rule_name   TEXT,
            device_ip   TEXT,
            detail      TEXT
        );
        CREATE TABLE IF NOT EXISTS geo_cache (
            ip      TEXT PRIMARY KEY,
            country TEXT,
            city    TEXT,
            isp     TEXT,
            ts      INTEGER
        );
        CREATE TABLE IF NOT EXISTS alert_rules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_type   TEXT,
            name        TEXT,
            params      TEXT,
            enabled     INTEGER DEFAULT 1
        );
        """
        with self._lock:
            self._conn.executescript(sql)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Device API
    # ------------------------------------------------------------------

    def upsert_device(self, device: Device) -> None:
        """Insert or update a device record.

        Args:
            device: Device object to persist.
        """
        with self._lock:
            self._devices[device.mac] = device
            self._conn.execute(
                """INSERT INTO devices (mac, ip, hostname, vendor, status, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(mac) DO UPDATE SET
                       ip=excluded.ip, hostname=excluded.hostname,
                       vendor=excluded.vendor, status=excluded.status,
                       last_seen=excluded.last_seen""",
                (
                    device.mac, device.ip, device.hostname, device.vendor,
                    device.status, device.first_seen.isoformat(),
                    device.last_seen.isoformat(),
                ),
            )
            self._conn.commit()

    def get_devices(self) -> list[Device]:
        """Return a snapshot of all known devices."""
        with self._lock:
            return list(self._devices.values())

    def get_device_by_ip(self, ip: str) -> Optional[Device]:
        """Return the device with the given IP, or None."""
        with self._lock:
            for d in self._devices.values():
                if d.ip == ip:
                    return d
            return None

    # ------------------------------------------------------------------
    # Connection API
    # ------------------------------------------------------------------

    def update_connection(self, conn: Connection) -> None:
        """Merge a new connection observation into the in-memory store.

        When the number of tracked connections reaches ``MAX_CONNECTIONS_MEMORY``
        the entry with the oldest ``last_seen`` is evicted to bound memory use.

        Args:
            conn: Connection object to merge/upsert.
        """
        with self._lock:
            key = conn.flow_key
            if key in self._connections:
                existing = self._connections[key]
                existing.add_bytes(conn.bytes_transferred)
                existing.dst_host = conn.dst_host or existing.dst_host
                existing.country = conn.country or existing.country
                existing.city = conn.city or existing.city
                existing.isp = conn.isp or existing.isp
                existing.flagged = existing.flagged or conn.flagged
            else:
                if len(self._connections) >= MAX_CONNECTIONS_MEMORY:
                    # Evict the entry with the oldest last_seen timestamp
                    oldest_key = min(
                        self._connections, key=lambda k: self._connections[k].last_seen
                    )
                    del self._connections[oldest_key]
                self._connections[key] = conn
            self._pending_connections.append(conn)

    def get_connections(self) -> list[Connection]:
        """Return a snapshot of all current in-memory connections."""
        with self._lock:
            return list(self._connections.values())

    def get_connections_for_device(self, ip: str) -> list[Connection]:
        """Return all connections whose source IP matches *ip*."""
        with self._lock:
            return [c for c in self._connections.values() if c.src_ip == ip]

    def flush_connections_to_db(self) -> None:
        """Batch-insert pending connections into ``connections_log``.

        Called on a timer every ``DB_WRITE_INTERVAL_SECONDS``.
        """
        with self._lock:
            if not self._pending_connections:
                return
            rows = [
                (
                    c.src_ip, c.dst_ip, c.dst_host, c.port, c.protocol,
                    c.service, c.bytes_transferred, c.country, c.city, c.isp,
                    c.first_seen.isoformat(), c.last_seen.isoformat(),
                    int(c.flagged),
                )
                for c in self._pending_connections
            ]
            self._pending_connections.clear()
            self._conn.executemany(
                """INSERT INTO connections_log
                   (src_ip, dst_ip, dst_host, port, protocol, service, bytes,
                    country, city, isp, first_seen, last_seen, flagged)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            self._conn.commit()
        logger.debug("Flushed %d connection rows to DB", len(rows))

    # ------------------------------------------------------------------
    # Bandwidth tracking
    # ------------------------------------------------------------------

    def record_bandwidth(self, direction: str, bytes_count: int) -> None:
        """Append a bandwidth sample.

        Args:
            direction: ``"in"`` or ``"out"``.
            bytes_count: Number of bytes in this sample.
        """
        ts = time.time()
        with self._lock:
            if direction == "in":
                self._bandwidth_in.append((ts, bytes_count))
            else:
                self._bandwidth_out.append((ts, bytes_count))

    def get_bandwidth_history(
        self, direction: str, window_seconds: int = 60
    ) -> list[tuple[float, int]]:
        """Return (timestamp, bytes) samples within the last *window_seconds*.

        Args:
            direction: ``"in"`` or ``"out"``.
            window_seconds: How far back to look.

        Returns:
            List of ``(timestamp, bytes)`` tuples sorted by timestamp.
        """
        cutoff = time.time() - window_seconds
        with self._lock:
            samples = self._bandwidth_in if direction == "in" else self._bandwidth_out
            return [(ts, b) for ts, b in samples if ts >= cutoff]

    def get_bandwidth_today(self) -> tuple[int, int]:
        """Return total bytes (in, out) recorded since midnight today.

        Uses the in-memory bandwidth samples which accumulate throughout
        the session.  Does not query the DB to avoid double-counting bytes
        that are already present in both the in-memory lists and
        ``connections_log``.

        Returns:
            Tuple ``(bytes_in, bytes_out)``.
        """
        midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        with self._lock:
            total_in = sum(b for ts, b in self._bandwidth_in if ts >= midnight)
            total_out = sum(b for ts, b in self._bandwidth_out if ts >= midnight)
        return total_in, total_out

    # ------------------------------------------------------------------
    # Geo cache
    # ------------------------------------------------------------------

    def get_geo_cached(self, ip: str) -> Optional[dict]:
        """Retrieve a cached geolocation record.

        Args:
            ip: IP address to look up.

        Returns:
            Dict with keys ``country``, ``city``, ``isp``, or ``None``.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT country, city, isp FROM geo_cache WHERE ip=?", (ip,)
            ).fetchone()
        return dict(row) if row else None

    def set_geo_cached(self, ip: str, country: str, city: str, isp: str) -> None:
        """Store a geolocation result in the cache.

        Args:
            ip: IP address.
            country: Country name.
            city: City name.
            isp: ISP/organisation name.
        """
        with self._lock:
            self._conn.execute(
                """INSERT INTO geo_cache (ip, country, city, isp, ts)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(ip) DO UPDATE SET
                       country=excluded.country, city=excluded.city,
                       isp=excluded.isp, ts=excluded.ts""",
                (ip, country, city, isp, int(time.time())),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Alert rules
    # ------------------------------------------------------------------

    def _load_alert_rules(self) -> None:
        """Load persisted alert rules from the database."""
        rows = self._conn.execute(
            "SELECT id, rule_type, name, params, enabled FROM alert_rules"
        ).fetchall()
        self._alert_rules = [dict(r) for r in rows]

    def get_alert_rules(self) -> list[dict]:
        """Return all alert rules."""
        with self._lock:
            return list(self._alert_rules)

    def add_alert_rule(self, rule_type: str, name: str, params: str) -> int:
        """Persist a new alert rule and return its database ID.

        Args:
            rule_type: One of ``"new_device"``, ``"bandwidth"``,
                ``"ip_comm"``, ``"port"``.
            name: Human-readable rule name.
            params: JSON-encoded rule parameters.

        Returns:
            The row ID of the new rule.
        """
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO alert_rules (rule_type, name, params) VALUES (?,?,?)",
                (rule_type, name, params),
            )
            self._conn.commit()
            rule = {"id": cur.lastrowid, "rule_type": rule_type, "name": name,
                    "params": params, "enabled": 1}
            self._alert_rules.append(rule)
            return cur.lastrowid

    def delete_alert_rule(self, rule_id: int) -> None:
        """Remove an alert rule by ID.

        Args:
            rule_id: Database row ID of the rule to delete.
        """
        with self._lock:
            self._conn.execute("DELETE FROM alert_rules WHERE id=?", (rule_id,))
            self._conn.commit()
            self._alert_rules = [r for r in self._alert_rules if r["id"] != rule_id]

    # ------------------------------------------------------------------
    # Alert log
    # ------------------------------------------------------------------

    def add_alert(self, rule_name: str, device_ip: str, detail: str) -> dict:
        """Record a fired alert.

        Args:
            rule_name: Name of the rule that triggered.
            device_ip: IP of the device involved.
            detail: Human-readable description.

        Returns:
            The alert record dict.
        """
        ts = datetime.now().isoformat()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO alerts_log (ts, rule_name, device_ip, detail) VALUES (?,?,?,?)",
                (ts, rule_name, device_ip, detail),
            )
            self._conn.commit()
            record = {
                "id": cur.lastrowid,
                "ts": ts,
                "rule_name": rule_name,
                "device_ip": device_ip,
                "detail": detail,
            }
            self._alert_log.append(record)
            return record

    def get_alert_log(self, limit: int = 500) -> list[dict]:
        """Return the most recent alert log entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of alert record dicts, newest first.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, ts, rule_name, device_ip, detail FROM alerts_log "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def purge_old_data(self, retention_days: int = DB_RETENTION_DAYS) -> None:
        """Delete connection log and alert log entries older than *retention_days*.

        Args:
            retention_days: Records older than this will be deleted.
        """
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        with self._lock:
            self._conn.execute(
                "DELETE FROM connections_log WHERE last_seen < ?", (cutoff,)
            )
            self._conn.execute(
                "DELETE FROM alerts_log WHERE ts < ?", (cutoff,)
            )
            self._conn.commit()
        logger.info("Purged data older than %s", cutoff)

    def close(self) -> None:
        """Flush pending writes and close the database connection."""
        self.flush_connections_to_db()
        self._conn.close()
        logger.info("DataStore closed")
