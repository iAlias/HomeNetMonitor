"""Unit tests for DeviceScanner."""
from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.data_store import DataStore
from src.core.device_scanner import DeviceScanner, _get_default_gateway_network
from src.models.device import Device
from src.utils.mac_vendor import MacVendorLookup


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_db(tmp_path: Path) -> DataStore:
    """Return a DataStore backed by a temp SQLite file."""
    return DataStore(db_path=tmp_path / "test.db")


@pytest.fixture()
def vendor_lookup(tmp_path: Path) -> MacVendorLookup:
    """Return a MacVendorLookup with a small in-memory OUI table."""
    import json

    oui_path = tmp_path / "mac_oui.json"
    oui_path.write_text(json.dumps({"A4C138": "Raspberry Pi Foundation"}))
    lkp = MacVendorLookup(oui_path)
    lkp.load()
    return lkp


# ---------------------------------------------------------------------------
# _get_default_gateway_network
# ---------------------------------------------------------------------------


def test_get_default_gateway_network_returns_cidr() -> None:
    """Should return a /24 CIDR string when netifaces works."""
    mock_gw = {"default": {2: ("192.168.1.1", "eth0")}}
    mock_addrs = {2: [{"addr": "192.168.1.100"}]}

    import src.core.device_scanner as ds_mod

    mock_ni = MagicMock()
    mock_ni.gateways.return_value = mock_gw
    mock_ni.AF_INET = 2
    mock_ni.ifaddresses.return_value = mock_addrs

    with patch.object(ds_mod, "netifaces", mock_ni):
        result = _get_default_gateway_network()

    assert result == "192.168.1.0/24"


def test_get_default_gateway_network_returns_none_on_error() -> None:
    """Should return None when netifaces raises."""
    import src.core.device_scanner as ds_mod

    mock_ni = MagicMock()
    mock_ni.gateways.side_effect = Exception("no network")

    with patch.object(ds_mod, "netifaces", mock_ni):
        result = _get_default_gateway_network()

    assert result is None


# ---------------------------------------------------------------------------
# DeviceScanner
# ---------------------------------------------------------------------------


def _make_arp_response(ip: str, mac: str):
    """Build a mock Scapy (answered, unanswered) pair."""
    rcv = MagicMock()
    rcv.psrc = ip
    rcv.hwsrc = mac
    return [(None, rcv)]


class TestDeviceScanner:
    """Tests for DeviceScanner._scan()."""

    def setup_method(self) -> None:
        """Construct shared test objects."""
        self.store = MagicMock(spec=DataStore)
        self.store.get_devices.return_value = []
        self.vendor = MagicMock(spec=MacVendorLookup)
        self.vendor.get_vendor.return_value = "Raspberry Pi Foundation"

        self.scanner = DeviceScanner(
            data_store=self.store,
            vendor_lookup=self.vendor,
            network="192.168.1.0/24",
        )
        # Replace pyqtSignal emit with a plain callable for unit testing
        self.scanner.device_found = MagicMock()
        self.scanner.scan_complete = MagicMock()
        self.scanner.error_occurred = MagicMock()

    def test_new_device_is_added(self) -> None:
        """A previously unseen device should be upserted and emitted."""
        answered = _make_arp_response("192.168.1.10", "a4:c1:38:11:22:33")

        import src.core.device_scanner as ds_mod

        with patch.object(ds_mod, "srp", return_value=(answered, [])):
            with patch.object(ds_mod, "Ether", MagicMock()):
                with patch.object(ds_mod, "ARP", MagicMock()):
                    self.scanner._scan("192.168.1.0/24")

        self.store.upsert_device.assert_called()
        self.scanner.device_found.emit.assert_called()
        device_arg = self.store.upsert_device.call_args[0][0]
        assert device_arg.ip == "192.168.1.10"
        assert device_arg.mac == "a4:c1:38:11:22:33"
        assert device_arg.vendor == "Raspberry Pi Foundation"

    def test_existing_device_is_updated(self) -> None:
        """A device already in the store should have last_seen refreshed."""
        existing = Device(
            ip="192.168.1.10",
            mac="a4:c1:38:11:22:33",
            first_seen=datetime(2024, 1, 1),
            last_seen=datetime(2024, 1, 1),
        )
        self.store.get_devices.return_value = [existing]

        answered = _make_arp_response("192.168.1.10", "a4:c1:38:11:22:33")

        import src.core.device_scanner as ds_mod

        with patch.object(ds_mod, "srp", return_value=(answered, [])):
            with patch.object(ds_mod, "Ether", MagicMock()):
                with patch.object(ds_mod, "ARP", MagicMock()):
                    self.scanner._scan("192.168.1.0/24")

        assert existing.status == "Online"
        assert existing.last_seen > datetime(2024, 1, 1)

    def test_absent_device_marked_offline(self) -> None:
        """A device not seen for > threshold seconds should become Offline."""
        from datetime import timedelta

        old_device = Device(
            ip="192.168.1.99",
            mac="ff:ff:ff:ff:ff:ff",
            last_seen=datetime.now() - timedelta(seconds=200),
        )
        self.store.get_devices.return_value = [old_device]

        import src.core.device_scanner as ds_mod

        # ARP scan returns nothing
        with patch.object(ds_mod, "srp", return_value=([], [])):
            with patch.object(ds_mod, "Ether", MagicMock()):
                with patch.object(ds_mod, "ARP", MagicMock()):
                    self.scanner._scan("192.168.1.0/24")

        assert old_device.status == "Offline"

    def test_permission_error_emits_signal(self) -> None:
        """A PermissionError should emit error_occurred."""
        import src.core.device_scanner as ds_mod

        with patch.object(ds_mod, "srp", side_effect=PermissionError("no perms")):
            with patch.object(ds_mod, "Ether", MagicMock()):
                with patch.object(ds_mod, "ARP", MagicMock()):
                    self.scanner._scan("192.168.1.0/24")

        self.scanner.error_occurred.emit.assert_called_once()
        msg = self.scanner.error_occurred.emit.call_args[0][0]
        assert "Administrator" in msg

    def test_mac_vendor_lookup(self) -> None:
        """Vendor should be fetched from MacVendorLookup for new devices."""
        self.vendor.get_vendor.return_value = "TestVendor Inc."
        answered = _make_arp_response("192.168.1.50", "de:ad:be:ef:11:22")

        import src.core.device_scanner as ds_mod

        with patch.object(ds_mod, "srp", return_value=(answered, [])):
            with patch.object(ds_mod, "Ether", MagicMock()):
                with patch.object(ds_mod, "ARP", MagicMock()):
                    self.scanner._scan("192.168.1.0/24")

        device_arg = self.store.upsert_device.call_args[0][0]
        assert device_arg.vendor == "TestVendor Inc."
