# HomeNetMonitor

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11+-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-blue.svg)
![Build EXE](https://github.com/iAlias/HomeNetMonitor/actions/workflows/build.yml/badge.svg)

> **Desktop Network Monitoring Tool for Windows** — monitor home network traffic in real time.

![Screenshot](docs/screenshot.png)

---

## Features

- 📊 **Live Traffic Dashboard** — bytes/sec in/out graph (last 60 seconds), KPI cards (devices, connections, bandwidth), top 5 destinations with country flags
- 💻 **Device Discovery** — ARP scan of your /24 LAN every 30 seconds; table shows IP, MAC, vendor, hostname, status
- 🔗 **Active Connections** — real-time table of all network flows with colour coding (green = safe, yellow = unknown, red = flagged)
- 🔔 **Alert Rules** — define custom alerts (new device, bandwidth threshold, IP communication, port activity) with Windows toast notifications
- 🌐 **Geolocation** — batch IP geolocation via ip-api.com (free, no key required)
- 🔍 **Reverse DNS** — async hostname resolution with caching
- 🏭 **Vendor Lookup** — offline MAC OUI → manufacturer lookup
- 💾 **SQLite Persistence** — connections log, alert log, geo cache, alert rules
- 🛡 **Graceful Degradation** — GUI launches even if packet capture fails (non-admin mode)

---

## Requirements

- **Windows 10 or 11** (x64)
- **Python 3.11+** (for running from source)
- **[Npcap](https://npcap.com)** — required for Scapy packet capture on Windows. Download and install before running.
- **Administrator privileges** — required for raw packet capture and ARP scanning

---

## Installation (from source)

```bash
git clone https://github.com/iAlias/HomeNetMonitor.git
cd HomeNetMonitor
pip install -r requirements.txt
```

Then run **as Administrator**:

```bash
python src/main.py
```

---

## Build EXE

```bash
pip install -r requirements.txt
pyinstaller build.spec
```

The executable will be at `dist/HomeNetMonitor.exe`. It requests UAC elevation automatically on launch.

---

## Architecture

```
HomeNetMonitor/
├── src/
│   ├── main.py                 ← Entry point, logging setup
│   ├── ui/
│   │   ├── main_window.py      ← QMainWindow, menu, status bar, thread orchestration
│   │   ├── dashboard_tab.py    ← Live graph (pyqtgraph) + KPI cards
│   │   ├── devices_tab.py      ← ARP-discovered device table
│   │   ├── connections_tab.py  ← Real-time connection table
│   │   └── alerts_tab.py       ← Rule editor + alert log
│   ├── core/
│   │   ├── packet_sniffer.py   ← Scapy sniff() in QThread → Connection signals
│   │   ├── device_scanner.py   ← ARP broadcast in QThread → Device signals
│   │   ├── dns_resolver.py     ← ThreadPoolExecutor reverse-DNS with cache
│   │   ├── geo_lookup.py       ← ip-api.com batch lookup, SQLite cache
│   │   └── data_store.py       ← In-memory + SQLite (devices, connections, alerts)
│   ├── models/
│   │   ├── device.py           ← Device dataclass
│   │   └── connection.py       ← Connection dataclass
│   └── utils/
│       ├── mac_vendor.py       ← OUI JSON → vendor name
│       └── constants.py        ← Paths, colours, port map, QSS theme
├── resources/
│   ├── mac_oui.json            ← Bundled OUI database
│   └── icon.ico                ← App icon
├── tests/
│   ├── test_device_scanner.py
│   ├── test_packet_sniffer.py
│   └── test_dns_resolver.py
├── build.spec                  ← PyInstaller (onefile, uac_admin=True)
├── requirements.txt
└── .github/workflows/build.yml ← Auto-build .exe on push to main
```

**Data flow:**

```
Npcap → scapy.sniff() → PacketSniffer (QThread)
                                │
                    packet_received(Connection)
                                │
                  ┌─────────────▼─────────────┐
                  │         MainWindow         │
                  │  DataStore ◄──────────────┤
                  │  GeoLookup (batch thread)  │
                  │  DnsResolver (pool)        │
                  └─────────────┬─────────────┘
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                   ▼
       DashboardTab       DevicesTab        ConnectionsTab
      (graph + KPIs)    (ARP scanner)      (flow table)
                                                    │
                                              AlertsTab
                                           (rule eval + log)
```

---

## Running Tests

```bash
pip install pytest
pytest tests/
```

> **Note:** Tests that exercise Scapy packet parsing require Scapy to be installed and will be skipped otherwise.

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

Please follow PEP 8, add type hints on all functions, and include docstrings on all public methods.

---

## License

This project is licensed under the [MIT License](LICENSE).
