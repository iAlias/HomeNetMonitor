"""App-wide constants and configuration defaults."""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Application identity
# ---------------------------------------------------------------------------
APP_NAME: str = "HomeNetMonitor"
APP_VERSION: str = "1.0.0"

# ---------------------------------------------------------------------------
# Filesystem paths
# ---------------------------------------------------------------------------
APPDATA_DIR: Path = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
DB_PATH: Path = APPDATA_DIR / "data.db"
LOG_PATH: Path = APPDATA_DIR / "app.log"

# Path to bundled resources (works both from source and PyInstaller onefile)
_HERE = Path(__file__).parent.parent.parent  # repo root when running from source
RESOURCES_DIR: Path = _HERE / "resources"
MAC_OUI_JSON: Path = RESOURCES_DIR / "mac_oui.json"
ICON_PATH: Path = RESOURCES_DIR / "icon.ico"

# ---------------------------------------------------------------------------
# Scanning / capture settings
# ---------------------------------------------------------------------------
ARP_SCAN_INTERVAL_SECONDS: int = 30
DEVICE_OFFLINE_THRESHOLD_SECONDS: int = 90
DNS_CACHE_TTL_SECONDS: int = 3600
DNS_LOOKUP_TIMEOUT_SECONDS: float = 2.0
GEO_BATCH_INTERVAL_SECONDS: int = 5
GEO_API_URL: str = "http://ip-api.com/batch"
GEO_API_RATE_LIMIT: int = 100  # max IPs per batch
DB_WRITE_INTERVAL_SECONDS: int = 10
DB_RETENTION_DAYS: int = 7
TRAFFIC_HISTORY_SECONDS: int = 60  # dashboard graph window
MAX_CONNECTIONS_MEMORY: int = 10_000  # max in-memory Connection entries

# ---------------------------------------------------------------------------
# GUI / styling
# ---------------------------------------------------------------------------
DARK_BG: str = "#1a1a2e"
ACCENT: str = "#00b4d8"
TEXT_COLOR: str = "#e0e0e0"
TABLE_ALT_ROW: str = "#16213e"
GREEN_SAFE: str = "#00c853"
YELLOW_UNKNOWN: str = "#ffd600"
RED_FLAGGED: str = "#d50000"

QSS_DARK_THEME: str = f"""
QMainWindow, QDialog, QWidget {{
    background-color: {DARK_BG};
    color: {TEXT_COLOR};
    font-family: Segoe UI, Arial, sans-serif;
    font-size: 13px;
}}
QTabBar::tab {{
    background: #16213e;
    color: {TEXT_COLOR};
    padding: 8px 20px;
    border: none;
}}
QTabBar::tab:selected {{
    background: {ACCENT};
    color: #000000;
    font-weight: bold;
}}
QTableWidget {{
    background-color: #16213e;
    alternate-background-color: {DARK_BG};
    color: {TEXT_COLOR};
    gridline-color: #2a2a4a;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: {ACCENT};
    color: #000000;
}}
QHeaderView::section {{
    background-color: #0f3460;
    color: {TEXT_COLOR};
    padding: 4px;
    border: none;
    font-weight: bold;
}}
QPushButton {{
    background-color: {ACCENT};
    color: #000000;
    border: none;
    padding: 6px 16px;
    border-radius: 4px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: #0090b8;
}}
QPushButton:disabled {{
    background-color: #444466;
    color: #888888;
}}
QLineEdit, QComboBox, QSpinBox {{
    background-color: #16213e;
    color: {TEXT_COLOR};
    border: 1px solid #2a2a4a;
    padding: 4px 8px;
    border-radius: 4px;
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: #16213e;
    color: {TEXT_COLOR};
    selection-background-color: {ACCENT};
}}
QStatusBar {{
    background-color: #0f3460;
    color: {TEXT_COLOR};
}}
QMenuBar {{
    background-color: #0f3460;
    color: {TEXT_COLOR};
}}
QMenuBar::item:selected {{
    background-color: {ACCENT};
    color: #000000;
}}
QMenu {{
    background-color: #16213e;
    color: {TEXT_COLOR};
    border: 1px solid #2a2a4a;
}}
QMenu::item:selected {{
    background-color: {ACCENT};
    color: #000000;
}}
QScrollBar:vertical {{
    background: #16213e;
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {ACCENT};
    border-radius: 5px;
}}
QLabel {{
    color: {TEXT_COLOR};
}}
QGroupBox {{
    border: 1px solid #2a2a4a;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
    color: {ACCENT};
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
}}
"""

# ---------------------------------------------------------------------------
# Well-known port → service name mapping
# ---------------------------------------------------------------------------
PORT_SERVICE_MAP: dict[int, str] = {
    20: "FTP-data",
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    67: "DHCP",
    68: "DHCP",
    80: "HTTP",
    110: "POP3",
    123: "NTP",
    143: "IMAP",
    161: "SNMP",
    162: "SNMP",
    194: "IRC",
    443: "HTTPS",
    445: "SMB",
    465: "SMTPS",
    500: "IKE/VPN",
    514: "Syslog",
    587: "SMTP",
    636: "LDAPS",
    853: "DNS-TLS",
    993: "IMAPS",
    995: "POP3S",
    1194: "OpenVPN",
    1433: "MSSQL",
    1723: "PPTP",
    3306: "MySQL",
    3389: "RDP",
    4444: "Metasploit",
    5900: "VNC",
    6881: "BitTorrent",
    8080: "HTTP-proxy",
    8443: "HTTPS-alt",
    9050: "Tor",
}

# ---------------------------------------------------------------------------
# Known-safe destination IP prefixes (rough)
# ---------------------------------------------------------------------------
SAFE_ASN_PREFIXES: list[str] = [
    "8.8.",      # Google DNS
    "8.34.",     # Google
    "8.35.",     # Google
    "34.",       # Google Cloud
    "35.",       # Google Cloud
    "142.250.",  # Google
    "172.217.",  # Google
    "216.58.",   # Google
    "1.1.",      # Cloudflare
    "1.0.0.",    # Cloudflare
    "104.16.",   # Cloudflare
    "104.17.",   # Cloudflare
    "13.64.",    # Microsoft Azure
    "20.0.",     # Microsoft Azure
    "40.64.",    # Microsoft
    "52.",       # AWS/Azure
]

# RFC 1918 private ranges (used by geo_lookup to skip lookups)
PRIVATE_PREFIXES: list[str] = [
    "10.",
    "192.168.",
    "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.",
    "172.24.", "172.25.", "172.26.", "172.27.",
    "172.28.", "172.29.", "172.30.", "172.31.",
    "127.",
    "169.254.",
    "::1",
    "fe80:",
]
