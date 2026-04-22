"""Connection dataclass for representing a network connection."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Connection:
    """Represents an active or recent network connection.

    Attributes:
        src_ip: Source IP address.
        dst_ip: Destination IP address.
        dst_host: Resolved hostname for dst_ip.
        port: Destination port number.
        protocol: "TCP", "UDP", or "Other".
        service: Human-readable service name (e.g., "HTTPS").
        bytes_transferred: Total bytes counted for this flow.
        country: Country of dst_ip from geolocation.
        city: City of dst_ip from geolocation.
        isp: ISP of dst_ip from geolocation.
        first_seen: When this connection was first observed.
        last_seen: Most recent packet timestamp.
        flagged: Whether this connection triggered an alert rule.
    """

    src_ip: str
    dst_ip: str
    dst_host: str = ""
    port: int = 0
    protocol: str = "Other"
    service: str = ""
    bytes_transferred: int = 0
    country: str = ""
    city: str = ""
    isp: str = ""
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    flagged: bool = False

    @property
    def flow_key(self) -> tuple:
        """Unique key identifying this flow."""
        return (self.src_ip, self.dst_ip, self.port, self.protocol)

    @property
    def duration_seconds(self) -> float:
        """Seconds since this connection was first observed."""
        return (self.last_seen - self.first_seen).total_seconds()

    def add_bytes(self, n: int) -> None:
        """Accumulate bytes and refresh last_seen."""
        self.bytes_transferred += n
        self.last_seen = datetime.now()

    def to_dict(self) -> dict:
        """Return a plain dict for serialisation."""
        return {
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "dst_host": self.dst_host,
            "port": self.port,
            "protocol": self.protocol,
            "service": self.service,
            "bytes_transferred": self.bytes_transferred,
            "country": self.country,
            "city": self.city,
            "isp": self.isp,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "flagged": self.flagged,
        }
