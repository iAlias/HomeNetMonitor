"""Unit tests for PacketSniffer."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.data_store import DataStore
from src.core.packet_sniffer import PacketSniffer
from src.models.connection import Connection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ip_pkt(src: str, dst: str, length: int = 100):
    """Build a mock Scapy IP packet."""
    pkt = MagicMock()
    pkt.__len__ = lambda self: length
    ip_layer = MagicMock()
    ip_layer.src = src
    ip_layer.dst = dst

    # Simulate layer containment checks
    def contains(layer_cls):
        from scapy.layers.inet import IP  # type: ignore

        return layer_cls is IP

    pkt.__contains__ = lambda self, cls: contains(cls)
    pkt.__getitem__ = lambda self, cls: ip_layer if cls.__name__ == "IP" else None
    return pkt


def _make_tcp_pkt(src: str, dst: str, dport: int = 443, length: int = 200):
    """Build a mock Scapy TCP/IP packet."""
    try:
        from scapy.layers.inet import IP, TCP  # type: ignore
    except ImportError:
        pytest.skip("scapy not installed")

    pkt = IP(src=src, dst=dst) / TCP(dport=dport)
    # Override len so it's predictable
    pkt.__len__ = lambda: length
    return pkt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_store(tmp_path: Path) -> DataStore:
    """Return a DataStore backed by a temp SQLite file."""
    return DataStore(db_path=tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPacketSniffer:
    """Tests for PacketSniffer._process() logic."""

    def setup_method(self) -> None:
        """Set up a sniffer with a real (temp) data store."""
        import tempfile

        self._tmpdir = tempfile.mkdtemp()
        self.store = DataStore(db_path=Path(self._tmpdir) / "test.db")
        self.sniffer = PacketSniffer(self.store, interface="eth0")
        self.sniffer.packet_received = MagicMock()
        self.sniffer.error_occurred = MagicMock()
        self.sniffer._local_prefix = "192.168.1."

    def teardown_method(self) -> None:
        """Close the store and remove the temp directory."""
        import shutil

        self.store.close()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_non_ip_packet_ignored(self) -> None:
        """A packet without an IP layer should be silently ignored."""
        try:
            from scapy.layers.inet import IP  # type: ignore
        except ImportError:
            pytest.skip("scapy not installed")

        pkt = MagicMock()
        pkt.__contains__ = lambda self, cls: False  # no IP layer

        self.sniffer._process(pkt)
        self.sniffer.packet_received.emit.assert_not_called()

    def test_tcp_packet_creates_connection(self) -> None:
        """A TCP packet should produce a Connection with correct attributes."""
        try:
            from scapy.layers.inet import IP, TCP  # type: ignore
        except ImportError:
            pytest.skip("scapy not installed")

        pkt = IP(src="192.168.1.10", dst="8.8.8.8") / TCP(dport=443)
        self.sniffer._process(pkt)
        self.sniffer.packet_received.emit.assert_called_once()
        conn: Connection = self.sniffer.packet_received.emit.call_args[0][0]
        assert conn.src_ip == "192.168.1.10"
        assert conn.dst_ip == "8.8.8.8"
        assert conn.protocol == "TCP"
        assert conn.port == 443
        assert conn.service == "HTTPS"

    def test_udp_packet_creates_connection(self) -> None:
        """A UDP packet should produce a Connection with UDP protocol."""
        try:
            from scapy.layers.inet import IP, UDP  # type: ignore
        except ImportError:
            pytest.skip("scapy not installed")

        pkt = IP(src="10.0.0.5", dst="1.1.1.1") / UDP(dport=53)
        self.sniffer._process(pkt)
        self.sniffer.packet_received.emit.assert_called_once()
        conn: Connection = self.sniffer.packet_received.emit.call_args[0][0]
        assert conn.protocol == "UDP"
        assert conn.port == 53
        assert conn.service == "DNS"

    def test_byte_counting_accumulates(self) -> None:
        """Multiple packets on the same flow should accumulate bytes."""
        try:
            from scapy.layers.inet import IP, TCP  # type: ignore
        except ImportError:
            pytest.skip("scapy not installed")

        pkt = IP(src="192.168.1.20", dst="172.217.1.1") / TCP(dport=80)
        for _ in range(3):
            self.sniffer._process(pkt)

        conns = self.store.get_connections()
        matching = [c for c in conns if c.src_ip == "192.168.1.20" and c.port == 80]
        assert matching, "Expected at least one matching connection"
        assert matching[0].bytes_transferred > 0

    def test_outbound_bytes_tracked(self) -> None:
        """Outbound packets (from local prefix) should increment _bytes_out."""
        try:
            from scapy.layers.inet import IP, TCP  # type: ignore
        except ImportError:
            pytest.skip("scapy not installed")

        before_out = self.sniffer._bytes_out
        pkt = IP(src="192.168.1.5", dst="8.8.8.8") / TCP(dport=443)
        self.sniffer._process(pkt)
        assert self.sniffer._bytes_out > before_out

    def test_inbound_bytes_tracked(self) -> None:
        """Inbound packets (from external IP) should increment _bytes_in."""
        try:
            from scapy.layers.inet import IP, TCP  # type: ignore
        except ImportError:
            pytest.skip("scapy not installed")

        before_in = self.sniffer._bytes_in
        pkt = IP(src="8.8.8.8", dst="192.168.1.5") / TCP(dport=12345)
        self.sniffer._process(pkt)
        assert self.sniffer._bytes_in > before_in

    def test_unknown_port_service_empty(self) -> None:
        """A port not in PORT_SERVICE_MAP should produce an empty service string."""
        try:
            from scapy.layers.inet import IP, TCP  # type: ignore
        except ImportError:
            pytest.skip("scapy not installed")

        pkt = IP(src="192.168.1.1", dst="5.5.5.5") / TCP(dport=9999)
        self.sniffer._process(pkt)
        conn: Connection = self.sniffer.packet_received.emit.call_args[0][0]
        assert conn.service == ""
