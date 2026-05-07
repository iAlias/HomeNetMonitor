"""Devices tab showing discovered LAN devices."""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.data_store import DataStore
from src.models.device import Device
from src.utils.constants import ACCENT, GREEN_SAFE, RED_FLAGGED

logger = logging.getLogger(__name__)


class DevicesTab(QWidget):
    """Tab that lists all discovered LAN devices with filtering.

    Emits :pyqt:`device_selected` when the user double-clicks a row or
    activates the *View Traffic* button.

    Args:
        data_store: Shared :class:`~src.core.data_store.DataStore`.
        parent: Parent widget.
    """

    device_selected = pyqtSignal(str)  # emits device IP

    _COLUMNS = [
        "IP Address",
        "MAC Address",
        "Vendor",
        "Hostname",
        "Status",
        "First Seen",
        "Last Seen",
    ]

    def __init__(self, data_store: DataStore, parent: Optional[QWidget] = None) -> None:
        """Initialise the devices tab."""
        super().__init__(parent)
        self._store = data_store
        self._setup_ui()
        self._start_refresh_timer()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the devices tab layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # ── Top toolbar ───────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self._count_label = QLabel("No devices discovered")
        self._count_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        toolbar.addWidget(self._count_label)
        toolbar.addStretch()
        self._view_traffic_btn = QPushButton("🔗  View Traffic")
        self._view_traffic_btn.setToolTip(
            "Open the Connections tab filtered by the selected device's IP"
        )
        self._view_traffic_btn.setEnabled(False)
        self._view_traffic_btn.clicked.connect(self._on_view_traffic)
        toolbar.addWidget(self._view_traffic_btn)
        root.addLayout(toolbar)

        # ── Search bar ────────────────────────────────────────────────
        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        search_row.addWidget(QLabel("🔍"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Filter by IP, MAC, hostname, or vendor…")
        self._search_edit.textChanged.connect(self._apply_filter)
        search_row.addWidget(self._search_edit)
        root.addLayout(search_row)

        # ── Stacked widget: table  ↔  empty state ─────────────────────
        self._stack = QStackedWidget()

        # Page 0 — device table
        self._table = QTableWidget(0, len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels(self._COLUMNS)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setMinimumSectionSize(80)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.setToolTip(
            "Double-click or press 'View Traffic' to filter Connections by this device"
        )
        self._stack.addWidget(self._table)

        # Page 1 — empty state
        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon = QLabel("🖥")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon.setStyleSheet("font-size: 48px;")
        empty_layout.addWidget(empty_icon)
        self._empty_label = QLabel(
            "No devices discovered yet.\n\n"
            "• Run the application as Administrator\n"
            "• Ensure Npcap is installed\n"
            "• Wait for the ARP scan (every 30 s)"
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            "color: #666688; font-size: 13px;"
        )
        empty_layout.addWidget(self._empty_label)
        self._stack.addWidget(empty_page)

        root.addWidget(self._stack)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _start_refresh_timer(self) -> None:
        """Start the 2-second UI refresh timer."""
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    def refresh(self) -> None:
        """Reload device data from the store and repaint the table."""
        devices = self._store.get_devices()
        filter_text = self._search_edit.text().lower()
        if filter_text:
            devices = [
                d
                for d in devices
                if filter_text in d.ip.lower()
                or filter_text in d.mac.lower()
                or filter_text in d.hostname.lower()
                or filter_text in d.vendor.lower()
            ]

        if not devices:
            self._stack.setCurrentIndex(1)
            self._count_label.setText("No devices discovered")
        else:
            self._stack.setCurrentIndex(0)
            self._table.setRowCount(len(devices))
            for row, dev in enumerate(devices):
                self._set_row(row, dev)
            self._table.resizeColumnsToContents()
            online = sum(1 for d in devices if d.status == "Online")
            total = len(devices)
            self._count_label.setText(
                f"{total} device{'s' if total != 1 else ''} ({online} online)"
            )

    def _set_row(self, row: int, dev: Device) -> None:
        """Populate a single table row from a Device.

        Args:
            row: Table row index.
            dev: Device object to display.
        """
        values = [
            dev.ip,
            dev.mac,
            dev.vendor or "Unknown",
            dev.hostname or "—",
            dev.status,
            dev.first_seen.strftime("%Y-%m-%d %H:%M:%S"),
            dev.last_seen.strftime("%Y-%m-%d %H:%M:%S"),
        ]
        color = QColor(GREEN_SAFE) if dev.status == "Online" else QColor(RED_FLAGGED)
        for col, val in enumerate(values):
            item = QTableWidgetItem(val)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            )
            if col == 4:  # Status column — coloured text
                item.setForeground(color)
            self._table.setItem(row, col, item)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _apply_filter(self) -> None:
        """Refresh the table whenever the search box changes."""
        self.refresh()

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        """Enable or disable the View Traffic button based on row selection."""
        self._view_traffic_btn.setEnabled(bool(self._table.selectedItems()))

    def _on_view_traffic(self) -> None:
        """Emit the selected device IP to navigate to the Connections tab."""
        row = self._table.currentRow()
        if row >= 0:
            ip_item = self._table.item(row, 0)
            if ip_item:
                self.device_selected.emit(ip_item.text())

    def _on_cell_double_clicked(self, row: int, _col: int) -> None:
        """Navigate to Connections filtered by the double-clicked device.

        Args:
            row: Double-clicked row.
            _col: Double-clicked column (unused).
        """
        ip_item = self._table.item(row, 0)
        if ip_item:
            self.device_selected.emit(ip_item.text())

    def _show_context_menu(self, pos) -> None:  # type: ignore[override]
        """Show the right-click context menu.

        Args:
            pos: Mouse position in widget coordinates.
        """
        row = self._table.rowAt(pos.y())
        if row < 0:
            return

        ip_item = self._table.item(row, 0)
        if not ip_item:
            return
        ip = ip_item.text()

        menu = QMenu(self)
        view_action = menu.addAction("🔗  View Traffic")
        menu.addSeparator()
        copy_action = menu.addAction("📋  Copy IP")
        resolve_action = menu.addAction("🔍  Resolve Hostname")
        block_action = menu.addAction("🚫  Block Device (Firewall)")
        action = menu.exec(self._table.viewport().mapToGlobal(pos))

        if action == view_action:
            self.device_selected.emit(ip)
        elif action == copy_action:
            QApplication.clipboard().setText(ip)
        elif action == resolve_action:
            self._resolve_hostname(ip)
        elif action == block_action:
            self._block_device(ip)

    def _resolve_hostname(self, ip: str) -> None:
        """Trigger a reverse-DNS lookup and update the device record.

        Args:
            ip: IP address to resolve.
        """
        import socket

        try:
            hostname, _, _ = socket.gethostbyaddr(ip)
            device = self._store.get_device_by_ip(ip)
            if device:
                device.hostname = hostname
                self._store.upsert_device(device)
            self.refresh()
        except socket.herror:
            pass

    def _block_device(self, ip: str) -> None:
        """Add a Windows Firewall outbound block rule for *ip*.

        Args:
            ip: IP address to block.
        """
        import subprocess

        rule_name = f"HomeNetMonitor_Block_{ip}"
        cmd = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={rule_name}", "dir=out", "action=block", f"remoteip={ip}",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.info("Firewall rule added to block %s", ip)
            else:
                logger.warning(
                    "Failed to add firewall rule for %s: %s", ip, result.stderr
                )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error adding firewall rule: %s", exc)

    def update_device(self, device: Device) -> None:
        """Called when the DeviceScanner emits device_found.

        Args:
            device: Updated Device object.
        """
        self.refresh()
