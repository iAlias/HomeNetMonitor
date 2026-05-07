"""Connections tab showing real-time active network connections."""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.data_store import DataStore
from src.models.connection import Connection
from src.utils.constants import (
    ACCENT,
    GREEN_SAFE,
    RED_FLAGGED,
    SAFE_ASN_PREFIXES,
    YELLOW_UNKNOWN,
)
from src.utils.formatting import format_bytes as _format_bytes

logger = logging.getLogger(__name__)


def _row_color(conn: Connection) -> Optional[QColor]:
    """Determine the highlight colour for a connection row.

    Returns:
        Green for known-safe destinations, red for flagged, yellow
        for unknown, or ``None`` for no highlight.

    Args:
        conn: Connection object to classify.
    """
    if conn.flagged:
        return QColor(RED_FLAGGED)
    for prefix in SAFE_ASN_PREFIXES:
        if conn.dst_ip.startswith(prefix):
            return QColor(GREEN_SAFE)
    if conn.country:
        return None  # geo resolved but unknown provider — neutral
    return QColor(YELLOW_UNKNOWN)


def _duration_str(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string like ``"2m 34s"``.
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"


class ConnectionsTab(QWidget):
    """Tab displaying all active connections with filtering.

    Args:
        data_store: Shared :class:`~src.core.data_store.DataStore`.
        parent: Parent widget.
    """

    _COLUMNS = [
        "Source IP",
        "Destination IP",
        "Destination Host",
        "Port",
        "Protocol",
        "Service",
        "Bytes",
        "Country",
        "Duration",
    ]

    def __init__(self, data_store: DataStore, parent: Optional[QWidget] = None) -> None:
        """Initialise the connections tab."""
        super().__init__(parent)
        self._store = data_store
        self._device_filter: str = ""
        self._setup_ui()
        self._start_refresh_timer()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the connections tab layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # ── Device filter banner (hidden when no device filter is set) ─
        self._filter_banner = QWidget()
        self._filter_banner.setStyleSheet(
            "background-color: #0f3460; border-radius: 4px;"
        )
        banner_row = QHBoxLayout(self._filter_banner)
        banner_row.setContentsMargins(10, 4, 10, 4)
        self._banner_label = QLabel("🔍 Showing traffic for: —")
        self._banner_label.setStyleSheet(
            f"color: {ACCENT}; font-weight: bold; background: transparent;"
        )
        banner_row.addWidget(self._banner_label)
        banner_row.addStretch()
        clear_btn = QPushButton("✕  Clear")
        clear_btn.setFixedWidth(72)
        clear_btn.setStyleSheet(
            "QPushButton { background: #c62828; color: white; padding: 2px 8px;"
            "  border-radius: 3px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { background: #e53935; }"
        )
        clear_btn.clicked.connect(self._clear_device_filter)
        banner_row.addWidget(clear_btn)
        self._filter_banner.hide()
        root.addWidget(self._filter_banner)

        # ── Filter row ────────────────────────────────────────────────
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("🔍"))

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("IP, host, port…")
        self._filter_edit.textChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._filter_edit, stretch=2)

        filter_row.addWidget(QLabel("Protocol:"))
        self._proto_combo = QComboBox()
        self._proto_combo.addItems(["All", "TCP", "UDP", "Other"])
        self._proto_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._proto_combo)

        filter_row.addWidget(QLabel("Country:"))
        self._country_edit = QLineEdit()
        self._country_edit.setPlaceholderText("e.g. Italy")
        self._country_edit.textChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._country_edit, stretch=1)

        root.addLayout(filter_row)

        # ── Connections table ─────────────────────────────────────────
        self._table = QTableWidget(0, len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels(self._COLUMNS)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        root.addWidget(self._table)

        # ── Bottom bar: colour legend + connection count ───────────────
        bottom_row = QHBoxLayout()
        for colour, label in (
            (GREEN_SAFE, "Known safe"),
            (YELLOW_UNKNOWN, "Unknown"),
            (RED_FLAGGED, "Flagged"),
        ):
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {colour};")
            bottom_row.addWidget(dot)
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #aaaaaa; font-size: 11px;")
            bottom_row.addWidget(lbl)
            bottom_row.addSpacing(16)
        bottom_row.addStretch()
        self._count_label = QLabel("0 connections")
        self._count_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        bottom_row.addWidget(self._count_label)
        root.addLayout(bottom_row)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _start_refresh_timer(self) -> None:
        """Start the 2-second refresh timer."""
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    def refresh(self) -> None:
        """Reload connection data from the store."""
        connections = self._store.get_connections()
        connections = self._apply_filters(connections)

        self._table.setRowCount(len(connections))
        for row, conn in enumerate(connections):
            self._set_row(row, conn)
        self._table.resizeColumnsToContents()

        count = len(connections)
        self._count_label.setText(
            f"{count} connection{'s' if count != 1 else ''}"
        )

    def _set_row(self, row: int, conn: Connection) -> None:
        """Populate a single table row.

        Args:
            row: Table row index.
            conn: Connection to display.
        """
        values = [
            conn.src_ip,
            conn.dst_ip,
            conn.dst_host or "",
            str(conn.port) if conn.port else "",
            conn.protocol,
            conn.service or "",
            _format_bytes(conn.bytes_transferred),
            conn.country or "",
            _duration_str(conn.duration_seconds),
        ]
        color = _row_color(conn)
        for col, val in enumerate(values):
            item = QTableWidgetItem(val)
            if color:
                item.setForeground(color)
            self._table.setItem(row, col, item)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _on_filter_changed(self) -> None:
        """Trigger a refresh when any filter input changes."""
        self.refresh()

    def _apply_filters(self, connections: list[Connection]) -> list[Connection]:
        """Apply all active filter criteria to *connections*.

        Args:
            connections: Unfiltered list.

        Returns:
            Filtered list.
        """
        text = self._filter_edit.text().lower()
        proto = self._proto_combo.currentText()
        country = self._country_edit.text().lower()

        result = []
        for c in connections:
            if self._device_filter and c.src_ip != self._device_filter:
                continue
            if text and not (
                text in c.src_ip.lower()
                or text in c.dst_ip.lower()
                or text in (c.dst_host or "").lower()
                or text in str(c.port)
            ):
                continue
            if proto != "All" and c.protocol != proto:
                continue
            if country and country not in (c.country or "").lower():
                continue
            result.append(c)
        return result

    def filter_by_device(self, ip: str) -> None:
        """Show only connections from *ip*.

        Args:
            ip: Source IP to filter by, or empty string to clear the filter.
        """
        self._device_filter = ip
        if ip:
            self._banner_label.setText(f"🔍 Showing traffic for:  {ip}")
            self._filter_banner.show()
        else:
            self._filter_banner.hide()
        self.refresh()

    def _clear_device_filter(self) -> None:
        """Clear the active device IP filter."""
        self.filter_by_device("")
