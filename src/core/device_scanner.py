"""ARP-based LAN device scanner running in a QThread."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.data_store import DataStore
from src.models.device import Device
from src.utils.constants import (
    ARP_SCAN_INTERVAL_SECONDS,
    DEVICE_OFFLINE_THRESHOLD_SECONDS,
)
from src.utils.mac_vendor import MacVendorLookup

logger = logging.getLogger(__name__)

# Module-level imports so tests can patch them at their canonical locations.
try:
    import netifaces  # type: ignore
except ImportError:  # pragma: no cover
    netifaces = None  # type: ignore

try:
    from scapy.layers.l2 import ARP, Ether  # type: ignore
    from scapy.sendrecv import srp  # type: ignore
except ImportError:  # pragma: no cover
    ARP = Ether = srp = None  # type: ignore


def _get_default_gateway_network() -> Optional[str]:
    """Return the /24 network of the default gateway interface.

    Returns:
        Network string such as ``"192.168.1.0/24"``, or ``None`` if it
        cannot be determined.
    """
    try:
        if netifaces is None:
            return None
        gws = netifaces.gateways()
        default_gw = gws.get("default", {})
        if not default_gw:
            return None

        # netifaces.AF_INET == 2
        af_inet = netifaces.AF_INET
        if af_inet not in default_gw:
            return None

        gw_ip, iface = default_gw[af_inet][:2]
        addrs = netifaces.ifaddresses(iface)
        if af_inet not in addrs:
            return None

        addr_info = addrs[af_inet][0]
        ip = addr_info.get("addr", "")
        if not ip:
            return None

        # Build a /24 from the host IP
        parts = ip.split(".")
        if len(parts) != 4:
            return None
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not determine default gateway network: %s", exc)
        return None


class DeviceScanner(QThread):
    """ARP broadcast scanner that discovers devices on the local /24 subnet.

    Emits :pyqt:`device_found` for each discovered device on every scan.
    Runs continuously until :meth:`stop` is called.

    Args:
        data_store: Shared :class:`~src.core.data_store.DataStore`.
        vendor_lookup: Initialised :class:`~src.utils.mac_vendor.MacVendorLookup`.
        scan_interval: Seconds between ARP sweeps.
        network: CIDR network to scan, e.g. ``"192.168.1.0/24"``.  If
            ``None`` the default gateway /24 is used.
    """

    device_found = pyqtSignal(object)  # emits Device instances
    scan_complete = pyqtSignal(int)    # emits count of online devices
    error_occurred = pyqtSignal(str)   # emits error message string

    def __init__(
        self,
        data_store: DataStore,
        vendor_lookup: MacVendorLookup,
        scan_interval: int = ARP_SCAN_INTERVAL_SECONDS,
        network: Optional[str] = None,
    ) -> None:
        """Initialise the scanner."""
        super().__init__()
        self._store = data_store
        self._vendor = vendor_lookup
        self._scan_interval = scan_interval
        self._network = network
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # QThread interface
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Thread entry point — loops until :meth:`stop` is called."""
        network = self._network or _get_default_gateway_network()
        if network is None:
            msg = "Could not determine local network for ARP scan."
            logger.error(msg)
            self.error_occurred.emit(msg)
            return

        logger.info("DeviceScanner starting on %s", network)
        while not self._stop_event.is_set():
            self._scan(network)
            self._stop_event.wait(timeout=self._scan_interval)

    def stop(self) -> None:
        """Signal the scan loop to stop and wait for the thread."""
        self._stop_event.set()
        self.wait(5000)

    # ------------------------------------------------------------------
    # Scan logic
    # ------------------------------------------------------------------

    def _scan(self, network: str) -> None:
        """Perform a single ARP sweep of *network*.

        Args:
            network: CIDR notation network, e.g. ``"192.168.1.0/24"``.
        """
        try:
            if srp is None or ARP is None or Ether is None:
                self.error_occurred.emit("Scapy is not installed.")
                return

            pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=network)
            answered, _ = srp(pkt, timeout=3, verbose=False, retry=1)
        except PermissionError:
            msg = (
                "Insufficient privileges for ARP scan.\n"
                "Run HomeNetMonitor as Administrator."
            )
            logger.error(msg)
            self.error_occurred.emit(msg)
            return
        except Exception as exc:  # noqa: BLE001
            logger.error("ARP scan error: %s", exc)
            self.error_occurred.emit(str(exc))
            return

        found_macs: set[str] = set()
        for _, rcv in answered:
            ip = rcv.psrc
            mac = rcv.hwsrc.lower()
            found_macs.add(mac)

            existing = next(
                (d for d in self._store.get_devices() if d.mac == mac), None
            )
            if existing:
                existing.ip = ip
                existing.update_seen()
                self._store.upsert_device(existing)
                self.device_found.emit(existing)
            else:
                vendor = self._vendor.get_vendor(mac)
                device = Device(
                    ip=ip,
                    mac=mac,
                    vendor=vendor,
                    first_seen=datetime.now(),
                    last_seen=datetime.now(),
                )
                self._store.upsert_device(device)
                self.device_found.emit(device)

        # Mark devices not seen in this scan as offline if they've been
        # absent for longer than DEVICE_OFFLINE_THRESHOLD_SECONDS.
        now = datetime.now()
        for device in self._store.get_devices():
            if device.mac not in found_macs:
                elapsed = (now - device.last_seen).total_seconds()
                if elapsed > DEVICE_OFFLINE_THRESHOLD_SECONDS:
                    device.mark_offline()
                    self._store.upsert_device(device)
                    self.device_found.emit(device)

        online_count = sum(
            1 for d in self._store.get_devices() if d.status == "Online"
        )
        self.scan_complete.emit(online_count)
        logger.debug("ARP scan complete: %d online devices", online_count)
