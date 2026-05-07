"""Scapy-based packet sniffer running in a dedicated QThread."""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.data_store import DataStore
from src.models.connection import Connection
from src.utils.constants import PORT_SERVICE_MAP

logger = logging.getLogger(__name__)


class PacketSniffer(QThread):
    """Capture live packets using Scapy and emit parsed :class:`Connection` objects.

    Each captured IP packet is parsed and emitted via :attr:`packet_received`.
    Bandwidth samples are recorded in the shared :class:`DataStore`.

    Args:
        data_store: Shared :class:`~src.core.data_store.DataStore`.
        interface: Network interface name to sniff on.  ``None`` means
            Scapy will pick the default interface.
    """

    packet_received = pyqtSignal(object)   # Connection
    error_occurred = pyqtSignal(str)       # error message
    stats_updated = pyqtSignal(int, int)   # bytes_in, bytes_out per second

    def __init__(
        self,
        data_store: DataStore,
        interface: Optional[str] = None,
    ) -> None:
        """Initialise the sniffer."""
        super().__init__()
        self._store = data_store
        self._interface = interface
        self._stop_event = threading.Event()

        # Per-second counters
        self._bytes_in: int = 0
        self._bytes_out: int = 0
        self._last_stat_ts: float = time.time()

        # Local subnet prefix for determining direction
        self._local_prefix: Optional[str] = None

    # ------------------------------------------------------------------
    # QThread interface
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Thread entry point — starts Scapy sniff loop."""
        self._local_prefix = self._detect_local_prefix()
        try:
            from scapy.sendrecv import sniff  # type: ignore

            logger.info(
                "PacketSniffer starting on interface=%s", self._interface or "default"
            )
            sniff(
                iface=self._interface,
                prn=self._handle_packet,
                store=False,
                stop_filter=lambda _: self._stop_event.is_set(),
            )
        except PermissionError:
            msg = (
                "Insufficient privileges for packet capture.\n"
                "Run HomeNetMonitor as Administrator."
            )
            logger.error(msg)
            self.error_occurred.emit(msg)
        except Exception as exc:  # noqa: BLE001
            logger.error("Sniffer error: %s", exc)
            self.error_occurred.emit(str(exc))

    def stop(self) -> None:
        """Signal the sniff loop to stop and wait for the thread."""
        self._stop_event.set()
        self.wait(5000)

    def set_interface(self, interface: str) -> None:
        """Change the capture interface.  Requires a restart to take effect.

        Args:
            interface: Interface name as a string.
        """
        self._interface = interface

    # ------------------------------------------------------------------
    # Packet processing
    # ------------------------------------------------------------------

    def _handle_packet(self, pkt) -> None:  # type: ignore[override]
        """Callback invoked by Scapy for every captured packet.

        Args:
            pkt: Raw Scapy packet object.
        """
        try:
            self._process(pkt)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Packet processing error: %s", exc)

    def _process(self, pkt) -> None:  # type: ignore[override]
        """Parse a packet and emit a :class:`Connection` signal.

        Args:
            pkt: Scapy packet object.
        """
        try:
            from scapy.layers.inet import IP, TCP, UDP  # type: ignore
        except ImportError:
            return

        if IP not in pkt:
            return

        ip_layer = pkt[IP]
        src_ip: str = ip_layer.src
        dst_ip: str = ip_layer.dst
        pkt_len: int = len(pkt)

        # Determine direction from local prefix
        if self._local_prefix:
            if src_ip.startswith(self._local_prefix):
                self._bytes_out += pkt_len
                self._store.record_bandwidth("out", pkt_len)
            else:
                self._bytes_in += pkt_len
                self._store.record_bandwidth("in", pkt_len)

        protocol = "Other"
        port = 0
        if TCP in pkt:
            protocol = "TCP"
            port = pkt[TCP].dport
        elif UDP in pkt:
            protocol = "UDP"
            port = pkt[UDP].dport

        # DNS hostname extraction
        dst_host = ""
        try:
            from scapy.layers.dns import DNS, DNSQR  # type: ignore

            if DNS in pkt and DNSQR in pkt:
                raw = pkt[DNSQR].qname
                dst_host = raw.decode("utf-8", errors="ignore").rstrip(".")
        except Exception:  # noqa: BLE001
            pass

        service = PORT_SERVICE_MAP.get(port, "")
        conn = Connection(
            src_ip=src_ip,
            dst_ip=dst_ip,
            dst_host=dst_host,
            port=port,
            protocol=protocol,
            service=service,
            bytes_transferred=pkt_len,
        )
        self._store.update_connection(conn)
        self.packet_received.emit(conn)

        # Emit per-second stats
        now = time.time()
        if now - self._last_stat_ts >= 1.0:
            self.stats_updated.emit(self._bytes_in, self._bytes_out)
            self._bytes_in = 0
            self._bytes_out = 0
            self._last_stat_ts = now

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_local_prefix() -> Optional[str]:
        """Return the first three octets of the outbound local IP address.

        Uses a UDP connect to an external address (no data is actually sent)
        to determine which interface the OS would use for outbound traffic.
        This avoids the common pitfall of ``socket.gethostbyname(hostname)``
        resolving to a loopback address on Linux.

        Returns:
            String such as ``"192.168.1."`` or ``None``.
        """
        import socket

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            parts = ip.split(".")
            if len(parts) == 4 and not ip.startswith("127."):
                return f"{parts[0]}.{parts[1]}.{parts[2]}."
        except Exception:  # noqa: BLE001
            pass
        return None
