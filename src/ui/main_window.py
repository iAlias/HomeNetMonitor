"""Main application window for HomeNetMonitor."""
from __future__ import annotations

import csv
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QWidget,
)

from src.core.data_store import DataStore
from src.core.device_scanner import DeviceScanner
from src.core.geo_lookup import GeoLookup
from src.core.packet_sniffer import PacketSniffer
from src.models.device import Device
from src.ui.alerts_tab import AlertsTab
from src.ui.connections_tab import ConnectionsTab
from src.ui.dashboard_tab import DashboardTab
from src.ui.devices_tab import DevicesTab
from src.utils.constants import (
    APP_NAME,
    APP_VERSION,
    DB_RETENTION_DAYS,
    DB_WRITE_INTERVAL_SECONDS,
    ICON_PATH,
    MAC_OUI_JSON,
    QSS_DARK_THEME,
)
from src.utils.mac_vendor import MacVendorLookup

logger = logging.getLogger(__name__)


def _is_admin() -> bool:
    """Return True if the process is running as administrator.

    Returns:
        ``True`` on Windows when the process has elevated privileges.
    """
    if sys.platform != "win32":
        return os.geteuid() == 0  # type: ignore[attr-defined]
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return False


class MainWindow(QMainWindow):
    """Top-level application window.

    Orchestrates all background threads and connects their signals to the UI.

    Args:
        data_store: Shared :class:`~src.core.data_store.DataStore`.
        settings: Application settings dict.
    """

    def __init__(
        self,
        data_store: DataStore,
        settings: Optional[dict] = None,
    ) -> None:
        """Initialise the main window."""
        super().__init__()
        self._store = data_store
        self._settings = settings or {}
        self._admin = _is_admin()

        self._vendor_lookup = MacVendorLookup(MAC_OUI_JSON)
        self._vendor_lookup.load()

        self._geo = GeoLookup(data_store)
        self._geo.start()

        self._setup_window()
        self._setup_tabs()
        self._setup_menu()
        self._setup_status_bar()
        self._start_background_services()
        self._start_maintenance_timer()

        if not self._admin:
            self._show_privilege_warning()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        """Configure the main window properties."""
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1024, 680)
        self.setStyleSheet(QSS_DARK_THEME)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

    def _setup_tabs(self) -> None:
        """Create and add all tab widgets."""
        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)

        self._dashboard_tab = DashboardTab(self._store)
        self._devices_tab = DevicesTab(self._store)
        self._connections_tab = ConnectionsTab(self._store)
        self._alerts_tab = AlertsTab(self._store)

        self._tabs.addTab(self._dashboard_tab, "📊  Dashboard")
        self._tabs.addTab(self._devices_tab, "💻  Devices")
        self._tabs.addTab(self._connections_tab, "🔗  Connections")
        self._tabs.addTab(self._alerts_tab, "🔔  Alerts")

        self.setCentralWidget(self._tabs)

        # Connect cross-tab interactions
        self._devices_tab.device_selected.connect(self._on_device_selected)
        self._alerts_tab.alert_fired.connect(self._on_alert_fired)

    def _setup_menu(self) -> None:
        """Build the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")
        file_menu.addAction("Export CSV…", self._export_csv)
        file_menu.addSeparator()
        file_menu.addAction("Settings…", self._open_settings)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        # Help menu
        help_menu = menubar.addMenu("Help")
        help_menu.addAction("About", self._show_about)

    def _setup_status_bar(self) -> None:
        """Create the status bar labels."""
        sb = self.statusBar()
        self._status_iface = QLabel("Interface: —")
        self._status_devices = QLabel("Devices: 0")
        self._status_connections = QLabel("Connections: 0")
        self._status_admin = QLabel(f"Admin: {'✓' if self._admin else '✗'}")
        self._status_admin.setStyleSheet(
            "color: #00c853;" if self._admin else "color: #d50000;"
        )
        for lbl in (
            self._status_iface,
            self._status_devices,
            self._status_connections,
            self._status_admin,
        ):
            sb.addPermanentWidget(lbl)
            sb.addPermanentWidget(QLabel("  |  "))

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(2000)
        self._status_timer.timeout.connect(self._update_status_bar)
        self._status_timer.start()

    # ------------------------------------------------------------------
    # Background services
    # ------------------------------------------------------------------

    def _start_background_services(self) -> None:
        """Start the packet sniffer and device scanner threads."""
        interface = self._settings.get("interface") or None

        # Packet sniffer
        self._sniffer = PacketSniffer(self._store, interface=interface)
        self._sniffer.error_occurred.connect(self._on_sniffer_error)
        self._sniffer.packet_received.connect(self._on_packet_received)
        if self._admin:
            self._sniffer.start()
        else:
            logger.warning("Not running as admin — packet capture disabled")

        # Device scanner
        scan_interval = self._settings.get("scan_interval", 30)
        self._scanner = DeviceScanner(
            self._store,
            self._vendor_lookup,
            scan_interval=scan_interval,
        )
        self._scanner.device_found.connect(self._on_device_found)
        self._scanner.error_occurred.connect(self._on_scanner_error)
        self._scanner.start()

        # DB flush timer
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(DB_WRITE_INTERVAL_SECONDS * 1000)
        self._flush_timer.timeout.connect(self._store.flush_connections_to_db)
        self._flush_timer.start()

        # Alert evaluation timer
        self._alert_timer = QTimer(self)
        self._alert_timer.setInterval(5000)
        self._alert_timer.timeout.connect(self._alerts_tab.evaluate_alerts)
        self._alert_timer.start()

        # Update status bar with current interface
        iface_name = interface or "default"
        self._status_iface.setText(f"Interface: {iface_name}")

    def _start_maintenance_timer(self) -> None:
        """Purge old DB data once per day (checked every hour)."""
        self._maint_timer = QTimer(self)
        self._maint_timer.setInterval(3_600_000)  # 1 hour
        retention = self._settings.get("retention_days", DB_RETENTION_DAYS)
        self._maint_timer.timeout.connect(lambda: self._store.purge_old_data(retention))
        self._maint_timer.start()

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_packet_received(self, conn) -> None:
        """Enqueue the destination IP for geolocation.

        Args:
            conn: :class:`~src.models.connection.Connection` object.
        """
        self._geo.enqueue(conn.dst_ip)

    def _on_device_found(self, device: Device) -> None:
        """Forward new device info to the devices tab.

        Args:
            device: Discovered or updated :class:`Device`.
        """
        self._devices_tab.update_device(device)
        logger.debug("Device found/updated: %s (%s)", device.ip, device.mac)

    def _on_device_selected(self, ip: str) -> None:
        """Switch to Connections tab filtered by *ip*.

        Args:
            ip: Source device IP to filter by.
        """
        self._connections_tab.filter_by_device(ip)
        self._tabs.setCurrentWidget(self._connections_tab)

    def _on_sniffer_error(self, message: str) -> None:
        """Show a dialog on packet sniffer errors.

        Args:
            message: Error message string.
        """
        QMessageBox.warning(
            self,
            "Packet Capture Error",
            message,
            QMessageBox.StandardButton.Ok,
        )

    def _on_scanner_error(self, message: str) -> None:
        """Show a dialog on device scanner errors.

        Args:
            message: Error message string.
        """
        QMessageBox.warning(
            self,
            "Device Scanner Error",
            message,
            QMessageBox.StandardButton.Ok,
        )

    def _on_alert_fired(self, rule_name: str, device_ip: str, detail: str) -> None:
        """Display a Windows toast notification when an alert fires.

        Args:
            rule_name: Name of the triggered rule.
            device_ip: Device IP address.
            detail: Human-readable alert detail.
        """
        if self._settings.get("alert_sound", True):
            self._show_toast(rule_name, detail)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _update_status_bar(self) -> None:
        """Refresh the status bar counters."""
        devices = self._store.get_devices()
        connections = self._store.get_connections()
        online = sum(1 for d in devices if d.status == "Online")
        self._status_devices.setText(f"Devices: {online}")
        self._status_connections.setText(f"Connections: {len(connections)}")

    # ------------------------------------------------------------------
    # Menu actions
    # ------------------------------------------------------------------

    def _export_csv(self) -> None:
        """Export all connections to a CSV file chosen by the user."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Connections", "", "CSV Files (*.csv)"
        )
        if not path:
            return
        connections = self._store.get_connections()
        if not connections:
            QMessageBox.information(self, "Export", "No connections to export.")
            return
        fieldnames = list(connections[0].to_dict().keys())
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for c in connections:
                writer.writerow(c.to_dict())
        QMessageBox.information(self, "Export Complete", f"Exported {len(connections)} connections.")

    def _open_settings(self) -> None:
        """Open the settings dialog."""
        from src.ui.settings_dialog import SettingsDialog

        dlg = SettingsDialog(self._settings, self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._settings.update(dlg.get_settings())

    def _show_about(self) -> None:
        """Show the About dialog."""
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<b>{APP_NAME}</b> v{APP_VERSION}<br>"
            "Desktop Network Monitoring Tool for Windows<br><br>"
            "Built with Python + PyQt6 + Scapy<br>"
            "© 2024 HomeNetMonitor contributors<br>"
            "<a href='https://github.com/iAlias/HomeNetMonitor'>GitHub</a>",
        )

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def _show_toast(self, title: str, message: str) -> None:
        """Show a Windows toast notification (best-effort).

        Falls back to a status bar message if toast is unavailable.

        Args:
            title: Notification title.
            message: Notification body text.
        """
        try:
            from win10toast import ToastNotifier  # type: ignore

            toaster = ToastNotifier()
            toaster.show_toast(
                f"{APP_NAME} — {title}",
                message,
                duration=5,
                threaded=True,
            )
        except ImportError:
            self.statusBar().showMessage(f"Alert: {title} — {message}", 8000)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Toast notification failed: %s", exc)
            self.statusBar().showMessage(f"Alert: {title} — {message}", 8000)

    # ------------------------------------------------------------------
    # Privilege warning
    # ------------------------------------------------------------------

    def _show_privilege_warning(self) -> None:
        """Show a non-blocking info bar about missing admin privileges."""
        self.statusBar().showMessage(
            "⚠  Not running as Administrator — packet capture and ARP scan are disabled.",
            0,  # persist until next message
        )

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Cleanly stop all background threads on close.

        Args:
            event: Qt close event.
        """
        self._sniffer.stop()
        self._scanner.stop()
        self._geo.stop()
        self._store.close()
        event.accept()
