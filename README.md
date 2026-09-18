# HomeNetMonitor

**A desktop home‑network monitor for Windows — live traffic graphs, device discovery and rule‑based alerts.**

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-blue.svg)](#system-requirements)
[![Build EXE](https://github.com/iAlias/HomeNetMonitor/actions/workflows/build.yml/badge.svg)](https://github.com/iAlias/HomeNetMonitor/actions/workflows/build.yml)

🇮🇹 [Leggi in italiano](README.it.md)

HomeNetMonitor is a PyQt6 desktop application that watches the traffic on your
home network in real time, discovers the devices connected to it, and raises
alerts when something looks suspicious — a new device joining, a burst of
bandwidth, traffic to a specific IP, or activity on a specific port. All the
data — connections, devices, alerts and the geolocation cache — is kept
locally in a SQLite database; nothing is sent anywhere except IP
geolocation lookups against the free [ip-api.com](http://ip-api.com) service.

---

## Contents

- [Quick start (no terminal required)](#quick-start-no-terminal-required)
- [Features](#features)
- [System requirements](#system-requirements)
- [Installation](#installation)
- [Running the application](#running-the-application)
- [User guide](#user-guide)
  - [Dashboard](#dashboard)
  - [Devices](#devices)
  - [Connections](#connections)
  - [Alerts](#alerts)
  - [Settings](#settings)
  - [CSV export](#csv-export)
- [Building the EXE](#building-the-exe)
- [Running the tests](#running-the-tests)
- [Project structure](#project-structure)
- [Data flow](#data-flow)
- [FAQ](#faq)
- [Contributing](#contributing)
- [License](#license)

---

## Quick start (no terminal required)

Don't want to use a terminal? You have two options.

### Option A — Download the ready‑made executable

1. Go to the [**Releases**](https://github.com/iAlias/HomeNetMonitor/releases/latest) page of the repository.
2. Download `HomeNetMonitor.exe` from the *Assets* section.
3. **Install [Npcap](https://npcap.com/#download)** (select *"Install Npcap in WinPcap API-compatible Mode"*).
4. Double‑click `HomeNetMonitor.exe`.
   Windows will show the UAC prompt asking for administrator privileges: click **Yes**.
   The GUI opens directly, with no terminal window at all.

> The EXE is built automatically by CI on every release. It does not require Python to be installed.

---

### Option B — Launch from the source folder with a double click

If you cloned the repository and have Python installed, you can use the
scripts in the `scripts/` folder:

| File | Description |
|---|---|
| `scripts/launch.vbs` | **Recommended** — starts the app with no visible terminal window |
| `scripts/launch.bat` | Alternative — opens a temporary terminal just long enough to start the GUI |

**Steps:**

1. Install Python 3.11+ and make sure it's on the PATH.
2. Install [Npcap](https://npcap.com/#download).
3. Double‑click `scripts/launch.vbs`.
   On first run, the virtual environment and dependencies are created automatically.
   The UAC prompt will appear — click **Yes**.
   The GUI opens.

---

## Features

| Feature | Description |
|---|---|
| 📊 **Live dashboard** | Bytes/sec graph (last 60 s), KPI cards (online devices, active connections, bandwidth), top 5 destinations with country flags |
| 💻 **Device discovery** | ARP scan of the local subnet every 30 s; table with IP, MAC, vendor, hostname, online/offline status |
| 🔗 **Active connections** | Real‑time table of all captured network flows with color coding (green = safe, yellow = unknown, red = flagged) |
| 🔔 **Alert rules** | Custom alerts for: new device, bandwidth threshold, communication with a specific IP, activity on a port |
| 🌐 **Geolocation** | Batch IP resolution via ip-api.com (free, no API key required) |
| 🔍 **Reverse DNS** | Asynchronous hostname resolution with a thread‑safe internal cache |
| 🏭 **Vendor lookup** | Manufacturer identification from the MAC address (OUI) via an offline database |
| 💾 **SQLite persistence** | Connection log, alert log, geolocation cache and alert rules stored locally |
| 🛡 **Unprivileged startup** | The GUI starts even without administrator rights (packet capture disabled, read‑only features still available) |

---

## System requirements

- **Operating system**: Windows 10 or Windows 11 (64‑bit)
- **Python**: version 3.11 or later ([download here](https://www.python.org/downloads/))
- **[Npcap](https://npcap.com/#download)**: packet‑capture library for Windows — **required** for the packet sniffer and ARP scan. Install it before running the application, choosing the *"Install Npcap in WinPcap API-compatible Mode"* option.
- **Administrator privileges**: required for raw packet capture and ARP scanning.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/iAlias/HomeNetMonitor.git
cd HomeNetMonitor
```

### 2. (Recommended) Create a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install the dependencies

```bash
pip install -r requirements.txt
```

Main dependencies:

| Package | Minimum version | Purpose |
|---|---|---|
| `PyQt6` | >= 6.6.0 | GUI framework |
| `pyqtgraph` | >= 0.13.3 | Live traffic graph |
| `scapy` | >= 2.5.0 | Packet capture and ARP scan |
| `psutil` | >= 5.9.8 | Network interface information |
| `netifaces2` | >= 0.0.1 | Gateway and subnet detection |
| `requests` | >= 2.31.0 | Geolocation API calls |
| `pyinstaller` | >= 6.4.0 | Standalone EXE packaging |

---

## Running the application

> **Always start the terminal or command prompt as Administrator** to enable packet capture and ARP scanning.

```bash
# With the virtual environment activated (from an Administrator prompt):
python src/main.py
```

On startup, the application:
1. Creates (if missing) the data folder at `%APPDATA%\HomeNetMonitor\`
2. Initializes the SQLite database (`data.db`) and the log file (`app.log`)
3. Starts the ARP scan and the packet sniffer in the background
4. Shows the main window

If the application is not run as administrator, the status bar shows:

> Not running as Administrator — packet capture and ARP scan are disabled.

In this case the GUI is still usable, but the data will not be updated in real time.

---

## User guide

### Dashboard

The Dashboard is the main screen shown at startup. It is divided into three sections.

#### Interface selector
At the top of the tab there is a dropdown to select the network interface to monitor. The active interface is also shown in the status bar at the bottom left.

#### KPI cards (Key Performance Indicators)
Four panels show, in real time:
- **Devices Online** — number of devices currently detected as active on the network
- **Active Connections** — number of active network flows in memory
- **Bandwidth Today (down)** — total bytes received since the start of the day (midnight)
- **Bandwidth Today (up)** — total bytes sent since the start of the day

Values refresh every 2 seconds.

#### Live traffic graph
The graph shows bytes per second for the last 60 seconds:
- **Blue line** — download traffic
- **Red line** — upload traffic

> The graph requires `pyqtgraph`. If it is not installed, an informational message is shown instead.

#### Top 5 destinations
Table with the 5 destinations that received the most bytes in the current session, with hostname, country (with flag emoji) and data volume.

---

### Devices

The **Devices** tab shows all the devices discovered through the ARP scan.

#### Device table

| Column | Content |
|---|---|
| IP Address | Current IPv4 address of the device |
| MAC Address | Physical MAC address |
| Vendor | Manufacturer identified from the MAC (OUI) |
| Hostname | Resolved host name (if available) |
| Status | **Online** (green) / **Offline** (red) |
| First Seen | Date and time of the first detection |
| Last Seen | Date and time of the last ARP response |

A device is marked **Offline** if it does not respond to ARP scans for more than 90 seconds.

#### Search bar
Type in the top bar to filter the list by IP, MAC, hostname or vendor. The filter applies in real time.

#### Context menu (right click)
Right‑click a device to access three actions:

- **Copy IP** — copies the IP address to the clipboard
- **Resolve Hostname** — performs a reverse DNS lookup and saves the result in the device record
- **Block Device (Firewall)** — adds a rule to the Windows Firewall to block outbound traffic to that device (requires administrator privileges)

#### Clicking a row
Clicking a device automatically switches to the **Connections** tab, filtered on that source IP.

---

### Connections

The **Connections** tab shows, in real time, all the network flows captured.

#### Connections table

| Column | Content |
|---|---|
| Source IP | Source IP (local device) |
| Destination IP | Destination IP |
| Destination Host | Hostname of the destination (if resolved via DNS) |
| Port | Destination port |
| Protocol | TCP / UDP / Other |
| Service | Service name (e.g. HTTPS, DNS, SSH) |
| Bytes | Total bytes transferred on this flow |
| Country | Destination country (from geolocation) |
| Duration | Duration of the flow since it started |

#### Color coding

| Color | Meaning |
|---|---|
| Green | Destination known to be safe (Google, Cloudflare, Microsoft Azure, AWS) |
| Yellow | Unknown destination (geolocation not resolved yet) |
| Red | Connection flagged by an alert rule |

#### Filters
- **Free text** — filters by source IP, destination IP, hostname or port number
- **Protocol** — filters by TCP, UDP, Other or all
- **Country** — filters by country name (e.g. "Italy", "United States")

---

### Alerts

The **Alerts** tab lets you configure monitoring rules and view the alert history.

#### Available alert rule types

| Type | Description | Parameters |
|---|---|---|
| **New Unknown Device** | Fires when a device not seen before appears | None |
| **Bandwidth Threshold** | Fires when a flow exceeds the threshold in MB | Device IP (or "any"), threshold in MB |
| **IP Communication** | Fires when a device communicates with a specific IP | Source IP (or "any"), destination IP |
| **Port Activity** | Fires when a specific port is used (e.g. 4444, 9050) | Device IP (or "any"), port number |

> Alerts are subject to a **60‑second cooldown** per (rule, device) pair, to avoid flooding the log.

#### Adding a rule

1. Click **Add Rule**
2. Enter a descriptive name in the *Rule Name* field
3. Choose the rule type from the *Rule Type* dropdown
4. Fill in the required parameters (fields change depending on the selected type)
5. Click **OK** to save

Input is validated before saving: the port must be an integer between 1 and 65535, and the bandwidth threshold must be a number.

#### Deleting a rule

Select the row in the rules table and click **Delete Selected**.

#### Alert log

The lower section shows the history of triggered alerts with:
- **Timestamp** — date and time of the event
- **Rule** — name of the triggered rule
- **Device IP** — IP address of the device involved
- **Detail** — detailed description of the event

The log refreshes every 3 seconds and shows the last 500 events. Alerts also generate a Windows toast notification (if the `win10toast` package is installed), or otherwise a message in the status bar.

---

### Settings

Open the settings from the **File -> Settings...** menu.

| Setting | Description | Default value |
|---|---|---|
| **Capture Interface** | Network interface to monitor | First available |
| **ARP Scan Interval** | ARP scan frequency in seconds (10–300 s) | 30 s |
| **DB Retention** | How many days to keep data in the database (1–365) | 7 days |
| **Alert Sound** | Enables Windows toast notifications for alerts | On |

> Changing the capture interface requires restarting the application for it to take effect.

---

### CSV export

Go to **File -> Export CSV...** to export all active connections to a CSV file.

The file contains the columns: `src_ip`, `dst_ip`, `dst_host`, `port`, `protocol`, `service`, `bytes_transferred`, `country`, `city`, `isp`, `first_seen`, `last_seen`, `flagged`.

---

## Building the EXE

To distribute the application as a standalone executable (without requiring Python to be installed):

```bash
pip install -r requirements.txt
pyinstaller build.spec
```

The executable is created at `dist/HomeNetMonitor.exe`. The `.spec` file is already configured for:
- *Onefile* mode (everything in a single `.exe`)
- Automatically requesting UAC elevation on startup (`uac_admin=True`)
- Bundling the resource files (`mac_oui.json`, `icon.ico`)

---

## Running the tests

```bash
pip install pytest
pytest tests/ -v
```

> Tests that rely on packet capture via Scapy are automatically skipped (`pytest.skip`) if Scapy is not installed.

The suite currently includes 24 tests covering:
- `DeviceScanner` — device discovery, offline handling, permissions
- `DnsResolver` — caching, timeouts, async lookups, eviction
- `PacketSniffer` — TCP/UDP packet parsing, byte counting

---

## Project structure

```
HomeNetMonitor/
├── src/
│   ├── main.py                 <- Entry point, logging configuration
│   ├── ui/
│   │   ├── main_window.py      <- QMainWindow, menu, status bar, thread orchestration
│   │   ├── dashboard_tab.py    <- Live graph (pyqtgraph) + KPI cards
│   │   ├── devices_tab.py      <- ARP devices table
│   │   ├── connections_tab.py  <- Real-time flows table
│   │   ├── alerts_tab.py       <- Rule editor + alert log
│   │   └── settings_dialog.py  <- Settings dialog
│   ├── core/
│   │   ├── packet_sniffer.py   <- Scapy sniff() in a QThread -> Connection signals
│   │   ├── device_scanner.py   <- ARP broadcast in a QThread -> Device signals
│   │   ├── dns_resolver.py     <- ThreadPoolExecutor reverse DNS with a thread-safe cache
│   │   ├── geo_lookup.py       <- Batch lookups against ip-api.com, SQLite cache
│   │   └── data_store.py       <- In-memory + SQLite storage (devices, connections, alerts)
│   ├── models/
│   │   ├── device.py           <- Device dataclass
│   │   └── connection.py       <- Connection dataclass
│   └── utils/
│       ├── mac_vendor.py       <- OUI JSON -> vendor name
│       ├── formatting.py       <- Shared formatting utilities (format_bytes)
│       └── constants.py        <- Paths, colors, port map, QSS theme
├── resources/
│   ├── mac_oui.json            <- Bundled OUI database
│   └── icon.ico                <- Application icon
├── tests/
│   ├── conftest.py             <- PyQt6 mocks for headless testing
│   ├── test_device_scanner.py
│   ├── test_packet_sniffer.py
│   └── test_dns_resolver.py
├── build.spec                  <- PyInstaller spec (onefile, uac_admin=True)
├── requirements.txt
└── .github/workflows/build.yml <- Automatic .exe build on push to main
```

---

## Data flow

```
Npcap -> scapy.sniff() -> PacketSniffer (QThread)
                                |
                    packet_received(Connection)
                                |
                  +-------------v-------------+
                  |         MainWindow         |
                  |  DataStore <--------------+|
                  |  GeoLookup (batch thread)  |
                  |  DnsResolver (pool)        |
                  +-------------+-------------+
                                |
              +-----------------+-----------------+
              v                 v                 v
       DashboardTab       DevicesTab        ConnectionsTab
      (graph + KPIs)     (ARP scanner)      (flows table)
                                                  |
                                            AlertsTab
                                     (rule evaluation + log)
```

**Persistence** — data is written to SQLite:
- every **10 seconds** (`flush_connections_to_db`)
- every **hour**, data older than the retention period is purged

---

## FAQ

**The application starts but I don't see any devices.**
Make sure you started it as Administrator and that Npcap is installed. Check the status bar: if it shows `Admin: X`, ARP scanning is disabled.

**The traffic graph is empty.**
The graph requires `pyqtgraph` and administrator privileges to capture packets. Verify the installation with `pip show pyqtgraph`.

**How do I block a device from the network?**
Go to the **Devices** tab, right‑click the device and choose **Block Device (Firewall)**. The application will add a rule to the Windows Firewall that blocks outbound traffic to that IP. To remove the rule, open Windows Defender Firewall and look for rules prefixed `HomeNetMonitor_Block_`.

**Alerts fire too often.**
Each (rule, device) pair has a 60‑second cooldown. If the log still fills up quickly, consider raising the thresholds or specifying a precise IP instead of "any".

**Where is the data stored?**
The database (`data.db`) and the log file (`app.log`) are located in `%APPDATA%\HomeNetMonitor\`.

**Geolocation doesn't work.**
HomeNetMonitor uses the free [ip-api.com](http://ip-api.com) service, which requires no registration. Check your internet connection. Private addresses (192.168.x.x, 10.x.x.x, etc.) are never geolocated by design.

---

## Contributing

1. Fork the repository
2. Create a branch: `git checkout -b feature/my-feature`
3. Make your changes and run the tests: `pytest tests/ -v`
4. Commit: `git commit -m "Add my feature"`
5. Push: `git push origin feature/my-feature`
6. Open a Pull Request

Please follow PEP 8, add type hints to all functions, and include docstrings on all public methods.

---

## License

This project is distributed under the [MIT license](LICENSE).
