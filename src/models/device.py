"""Device dataclass for representing a network device."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Device:
    """Represents a network device discovered on the LAN.

    Attributes:
        ip: IPv4 address of the device.
        mac: MAC address of the device.
        hostname: Resolved hostname, or empty string if unknown.
        vendor: Manufacturer name derived from MAC OUI.
        status: "Online" or "Offline".
        first_seen: Timestamp of first detection.
        last_seen: Timestamp of most recent detection.
    """

    ip: str
    mac: str
    hostname: str = ""
    vendor: str = ""
    status: str = "Online"
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)

    def update_seen(self) -> None:
        """Mark the device as online and refresh last_seen timestamp."""
        self.last_seen = datetime.now()
        self.status = "Online"

    def mark_offline(self) -> None:
        """Mark the device as offline."""
        self.status = "Offline"

    def to_dict(self) -> dict:
        """Return a plain dict for serialisation."""
        return {
            "ip": self.ip,
            "mac": self.mac,
            "hostname": self.hostname,
            "vendor": self.vendor,
            "status": self.status,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
        }
